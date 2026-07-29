import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from stair_agent.config import EnvironmentConfig
from stair_agent.game_state import GamePhase
from stair_agent.gym_env import (
    FeatureEncoder,
    GymEnvironmentError,
    RewardCalculator,
    StairAgentEnv,
)
from stair_agent.input_controller import Action
from stair_agent.observation import GameObservation


def observation(
    *,
    phase="playing",
    events=None,
    health=12,
    health_delta=0,
):
    return GameObservation(
        timestamp=1.0,
        phase=phase,
        player={
            "center_x": 200.0,
            "center_y": 160.0,
            "velocity_x": 20.0,
            "velocity_y": -30.0,
            "motion": "rising",
            "confidence": 0.9,
        },
        health={
            "segments": health,
            "delta": health_delta,
            "event": "unchanged",
        },
        nearest_platform={
            "track_id": 7,
            "kind": "normal",
            "confidence": 0.98,
            "box": {"left": 160, "top": 200, "width": 96, "height": 16},
            "vertical_gap": 13,
        },
        platforms=[
            {
                "track_id": 7,
                "kind": "normal",
                "confidence": 0.98,
                "box": {
                    "left": 160,
                    "top": 200,
                    "width": 96,
                    "height": 16,
                },
            }
        ],
        platform_scroll_velocity_y=-80.0,
        events=events or [],
    )


class FakeAdapter:
    def __init__(self, reset_observation=None, step_observations=None):
        self.reset_observation = reset_observation or observation()
        self.step_observations = list(step_observations or [observation()])
        self.actions = []
        self.release_count = 0
        self.closed = False

    def reset(self):
        return self.reset_observation

    def step(self, action):
        self.actions.append(action)
        if self.step_observations:
            return self.step_observations.pop(0)
        return observation()

    def release_all(self):
        self.release_count += 1

    def close(self):
        self.closed = True


def test_feature_encoder_returns_observation_space_value() -> None:
    encoder = FeatureEncoder(reference_width=634, reference_height=431)

    features = encoder.encode(observation(health=8, health_delta=-4))

    assert features.shape == (64,)
    assert features.dtype == np.float32
    assert encoder.space.contains(features)
    assert features[6] == pytest.approx(8 / 12)
    assert features[16] == 1.0
    assert features[17] == pytest.approx(8 / 634)
    assert features[18] == pytest.approx(40 / 431)
    assert features[19] == pytest.approx(96 / 634)
    assert features[20] == pytest.approx(16 / 431)
    assert features[21] == 0.0


def test_reward_uses_floor_progress_and_raw_damage() -> None:
    calculator = RewardCalculator(
        floor_reward=1.0,
        damage_penalty_per_segment=0.2,
        death_penalty=5.0,
    )
    item = observation(
        events=[
            {"type": "floor_descended"},
            {"type": "damage", "health_delta": -4},
        ],
        health=8,
        health_delta=-4,
    )

    assert calculator.calculate(item, terminated=False) == pytest.approx(0.2)
    assert calculator.calculate(item, terminated=True) == pytest.approx(-4.8)


def test_environment_maps_actions_and_returns_gym_tuple() -> None:
    adapter = FakeAdapter(
        step_observations=[
            observation(events=[{"type": "floor_descended"}])
        ]
    )
    env = StairAgentEnv(adapter, EnvironmentConfig(max_episode_steps=10))
    initial, info = env.reset()

    result, reward, terminated, truncated, step_info = env.step(1)

    assert env.observation_space.contains(initial)
    assert env.last_observation is not None
    assert info["phase"] == "playing"
    assert adapter.actions == [Action.LEFT]
    assert env.observation_space.contains(result)
    assert reward == 1.0
    assert not terminated
    assert not truncated
    assert step_info["events"] == ["floor_descended"]


def test_dialog_terminates_episode_and_releases_keys() -> None:
    adapter = FakeAdapter(
        step_observations=[observation(phase="dialog")]
    )
    env = StairAgentEnv(adapter, EnvironmentConfig(death_penalty=5.0))
    env.reset()

    _obs, reward, terminated, truncated, _info = env.step(0)

    assert reward == -5.0
    assert terminated
    assert not truncated
    assert adapter.release_count >= 1


def test_step_limit_truncates_episode() -> None:
    adapter = FakeAdapter()
    env = StairAgentEnv(adapter, EnvironmentConfig(max_episode_steps=1))
    env.reset()

    _obs, _reward, terminated, truncated, _info = env.step(0)

    assert not terminated
    assert truncated
    assert adapter.release_count >= 1


def test_adapter_exception_always_releases_keys() -> None:
    class BrokenAdapter(FakeAdapter):
        def step(self, action):
            raise RuntimeError("capture failed")

    adapter = BrokenAdapter()
    env = StairAgentEnv(adapter)
    env.reset()

    with pytest.raises(RuntimeError, match="capture failed"):
        env.step(2)

    assert adapter.release_count >= 1


def test_reset_requires_playing_phase() -> None:
    adapter = FakeAdapter(reset_observation=observation(phase="dialog"))
    env = StairAgentEnv(adapter)

    with pytest.raises(GymEnvironmentError, match="PLAYING"):
        env.reset()

    assert adapter.release_count >= 1


def test_environment_passes_gymnasium_checker_with_mock_adapter() -> None:
    env = StairAgentEnv(FakeAdapter())

    check_env(env, skip_render_check=True)

    env.close()
