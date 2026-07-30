from dataclasses import replace

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
    player_x=200.0,
):
    return GameObservation(
        timestamp=1.0,
        phase=phase,
        player={
            "center_x": player_x,
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
        step_penalty=0.01,
    )
    item = observation(
        events=[
            {"type": "floor_descended"},
            {"type": "damage", "health_delta": -4},
        ],
        health=8,
        health_delta=-4,
    )

    assert calculator.calculate(item, terminated=False) == pytest.approx(0.19)
    assert calculator.calculate(item, terminated=True) == pytest.approx(-4.81)


def test_reward_tracks_horizontal_progress_to_same_safe_platform() -> None:
    calculator = RewardCalculator(
        playfield_left=0,
        playfield_right=400,
        platform_alignment_reward_scale=0.5,
        platform_alignment_min_vertical_gap=25,
        platform_alignment_max_vertical_gap=260,
        platform_alignment_landing_margin=10,
    )

    def falling(player_x):
        item = observation(player_x=player_x)
        return replace(
            item,
            player={**item.player, "motion": "falling"},
        )

    assert calculator.calculate(
        falling(100),
        terminated=False,
        action=Action.RIGHT,
    ) == pytest.approx(0.0)
    assert calculator.calculate(
        falling(120),
        terminated=False,
        action=Action.RIGHT,
    ) == pytest.approx(0.025)
    assert calculator.last_components["platform_alignment_reward"] == pytest.approx(
        0.025
    )
    assert calculator.calculate(
        falling(90),
        terminated=False,
        action=Action.LEFT,
    ) == pytest.approx(-0.0375)


def test_reward_ignores_unsafe_platform_for_alignment() -> None:
    calculator = RewardCalculator(
        platform_alignment_reward_scale=0.5,
    )
    item = observation(player_x=100)
    unsafe = replace(
        item,
        player={**item.player, "motion": "falling"},
        platforms=[{**item.platforms[0], "kind": "spikes"}],
    )

    assert calculator.calculate(
        unsafe,
        terminated=False,
        action=Action.RIGHT,
    ) == pytest.approx(0.0)
    assert calculator.last_components["platform_alignment_target_id"] is None


def test_reward_excludes_launch_origin_while_rising() -> None:
    calculator = RewardCalculator(
        platform_alignment_reward_scale=0.5,
        platform_alignment_rising_origin_exclusion_gap=80,
    )
    item = observation(player_x=100)
    next_platform = {
        "track_id": 8,
        "kind": "normal",
        "confidence": 0.98,
        "box": {
            "left": 260,
            "top": 300,
            "width": 96,
            "height": 16,
        },
    }
    rising = replace(
        item,
        platforms=[item.platforms[0], next_platform],
    )

    calculator.calculate(
        rising,
        terminated=False,
        action=Action.RIGHT,
    )

    assert calculator.last_components["platform_alignment_target_id"] == 8


@pytest.mark.parametrize(
    ("player_x", "action", "expected"),
    [
        (100, Action.RIGHT, 0.05),
        (100, Action.LEFT, -0.05),
        (100, Action.RELEASE_ALL, -0.025),
        (300, Action.LEFT, 0.05),
        (300, Action.RIGHT, -0.05),
    ],
)
def test_reward_teaches_action_toward_safe_platform(
    player_x: float,
    action: Action,
    expected: float,
) -> None:
    item = observation(player_x=player_x)
    falling = replace(
        item,
        player={**item.player, "motion": "falling"},
    )
    calculator = RewardCalculator(
        platform_target_action_reward=0.05,
    )

    reward = calculator.calculate(
        falling,
        terminated=False,
        action=action,
    )

    assert reward == pytest.approx(expected)
    assert calculator.last_components["platform_target_action_reward"] == (
        pytest.approx(expected)
    )


def test_reward_penalizes_only_recent_direction_reversal_and_resets() -> None:
    calculator = RewardCalculator(
        step_penalty=0.0,
        direction_change_penalty=0.05,
        direction_change_window_steps=2,
    )
    item = observation()

    assert calculator.calculate(
        item,
        terminated=False,
        action=Action.LEFT,
    ) == 0.0
    assert calculator.calculate(
        item,
        terminated=False,
        action=Action.RELEASE_ALL,
    ) == 0.0
    assert calculator.calculate(
        item,
        terminated=False,
        action=Action.RIGHT,
    ) == pytest.approx(-0.05)
    assert calculator.last_components["direction_changed"]
    assert calculator.last_components["direction_change_penalty"] == pytest.approx(
        -0.05
    )

    calculator.reset()

    assert calculator.calculate(
        item,
        terminated=False,
        action=Action.RIGHT,
    ) == 0.0
    assert not calculator.last_components["direction_changed"]

    calculator.reset()
    calculator.calculate(item, terminated=False, action=Action.LEFT)
    for _ in range(3):
        calculator.calculate(
            item,
            terminated=False,
            action=Action.RELEASE_ALL,
        )

    assert calculator.calculate(
        item,
        terminated=False,
        action=Action.RIGHT,
    ) == 0.0
    assert not calculator.last_components["direction_changed"]


def test_reward_penalizes_spike_contact_only_after_grace_steps() -> None:
    item = observation()
    spike = replace(
        item,
        nearest_platform={
            **item.nearest_platform,
            "kind": "spikes",
            "vertical_gap": 6,
        },
    )
    calculator = RewardCalculator(
        step_penalty=0.0,
        spike_dwell_penalty=0.03,
        spike_dwell_grace_steps=2,
        spike_contact_max_gap=12,
    )

    first = calculator.calculate(
        spike,
        terminated=False,
        action=Action.RELEASE_ALL,
    )
    second = calculator.calculate(
        spike,
        terminated=False,
        action=Action.RELEASE_ALL,
    )
    third = calculator.calculate(
        spike,
        terminated=False,
        action=Action.RELEASE_ALL,
    )

    assert first == 0.0
    assert second == 0.0
    assert third == pytest.approx(-0.03)
    assert calculator.last_components["spike_contact"]
    assert calculator.last_components["spike_dwell_steps"] == 3
    assert calculator.last_components["spike_dwell_penalty"] == pytest.approx(
        -0.03
    )

    calculator.calculate(
        item,
        terminated=False,
        action=Action.RELEASE_ALL,
    )

    assert not calculator.last_components["spike_contact"]
    assert calculator.last_components["spike_dwell_steps"] == 0


def test_reward_penalizes_idle_action_only_after_grace_and_resets() -> None:
    calculator = RewardCalculator(
        step_penalty=0.0,
        idle_action_penalty=0.02,
        idle_action_grace_steps=2,
    )
    item = observation()

    first = calculator.calculate(
        item,
        terminated=False,
        action=Action.RELEASE_ALL,
    )
    second = calculator.calculate(
        item,
        terminated=False,
        action=Action.RELEASE_ALL,
    )
    third = calculator.calculate(
        item,
        terminated=False,
        action=Action.RELEASE_ALL,
    )

    assert first == 0.0
    assert second == 0.0
    assert third == pytest.approx(-0.02)
    assert calculator.last_components["idle_action_steps"] == 3
    assert calculator.last_components["idle_action_penalty"] == pytest.approx(
        -0.02
    )

    calculator.calculate(
        item,
        terminated=False,
        action=Action.LEFT,
    )

    assert calculator.last_components["idle_action_steps"] == 0
    assert calculator.last_components["idle_action_penalty"] == 0.0


def test_reward_penalizes_same_platform_dwell_and_new_platform_resets() -> None:
    calculator = RewardCalculator(
        step_penalty=0.0,
        platform_dwell_penalty=0.02,
        platform_dwell_grace_steps=2,
        platform_dwell_max_gap=80,
    )
    item = observation()

    first = calculator.calculate(
        item,
        terminated=False,
        action=Action.LEFT,
    )
    second = calculator.calculate(
        item,
        terminated=False,
        action=Action.LEFT,
    )
    third = calculator.calculate(
        item,
        terminated=False,
        action=Action.LEFT,
    )

    assert first == 0.0
    assert second == 0.0
    assert third == pytest.approx(-0.02)
    assert calculator.last_components["platform_dwell_steps"] == 3
    assert calculator.last_components["platform_dwell_penalty"] == pytest.approx(
        -0.02
    )

    next_platform = replace(
        item,
        nearest_platform={
            **item.nearest_platform,
            "track_id": 8,
        },
    )
    calculator.calculate(
        next_platform,
        terminated=False,
        action=Action.LEFT,
    )

    assert calculator.last_components["platform_dwell_steps"] == 1
    assert calculator.last_components["platform_dwell_penalty"] == 0.0


def test_reward_penalizes_top_danger_after_grace_steps() -> None:
    item = observation()
    top_player = replace(
        item,
        player={
            **item.player,
            "center_y": 100.0,
        },
    )
    calculator = RewardCalculator(
        step_penalty=0.0,
        reference_height=431,
        top_danger_penalty=0.03,
        top_danger_grace_steps=2,
        top_danger_y_ratio=0.33,
    )

    calculator.calculate(
        top_player,
        terminated=False,
        action=Action.LEFT,
    )
    calculator.calculate(
        top_player,
        terminated=False,
        action=Action.LEFT,
    )
    reward = calculator.calculate(
        top_player,
        terminated=False,
        action=Action.LEFT,
    )

    assert reward == pytest.approx(-0.03)
    assert calculator.last_components["top_danger"]
    assert calculator.last_components["top_danger_steps"] == 3
    assert calculator.last_components["top_danger_penalty"] == pytest.approx(
        -0.03
    )


@pytest.mark.parametrize(
    ("player_x", "action", "expected_wall"),
    [
        (35.0, Action.LEFT, "left"),
        (35.0, Action.RIGHT, None),
        (396.0, Action.RIGHT, "right"),
        (396.0, Action.LEFT, None),
        (200.0, Action.LEFT, None),
    ],
)
def test_reward_penalizes_only_actions_pushing_outward_at_playfield_wall(
    player_x: float,
    action: Action,
    expected_wall: str | None,
) -> None:
    calculator = RewardCalculator(
        step_penalty=0.0,
        playfield_left=24,
        playfield_right=407,
        wall_margin_pixels=20,
        wall_push_penalty=0.05,
    )
    item = observation(player_x=player_x)

    reward = calculator.calculate(
        item,
        terminated=False,
        action=action,
    )

    assert calculator.last_components["wall_push"] == expected_wall
    assert calculator.last_components["wall_push_penalty"] == (
        pytest.approx(-0.05) if expected_wall else 0.0
    )
    assert reward == (
        pytest.approx(-0.05) if expected_wall else 0.0
    )


def test_environment_maps_actions_and_returns_gym_tuple() -> None:
    adapter = FakeAdapter(
        step_observations=[
            observation(events=[{"type": "floor_descended"}])
        ]
    )
    env = StairAgentEnv(
        adapter,
        EnvironmentConfig(max_episode_steps=10, step_penalty=0.0),
    )
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
    assert "reward_components" in step_info


def test_environment_stacks_recent_features_and_action_history() -> None:
    adapter = FakeAdapter(
        step_observations=[observation(player_x=300.0)]
    )
    env = StairAgentEnv(
        adapter,
        EnvironmentConfig(
            observation_history_frames=3,
            include_action_history=True,
        ),
    )

    initial, info = env.reset()
    result, *_rest = env.step(1)
    initial_chunks = initial.reshape(3, 67)
    result_chunks = result.reshape(3, 67)

    assert initial.shape == (201,)
    assert info["history_frames"] == 3
    assert info["raw_feature_count"] == 64
    assert np.all(initial_chunks[:, 64:] == 0.0)
    assert np.allclose(initial_chunks[0, :64], initial_chunks[2, :64])
    assert result_chunks[-1, 1] == pytest.approx(300 / 634)
    assert result_chunks[-1, 64:].tolist() == [0.0, 1.0, 0.0]
    assert result_chunks[-2, 1] == pytest.approx(200 / 634)
    assert env.observation_space.contains(result)


def test_reset_clears_temporal_action_history() -> None:
    adapter = FakeAdapter(
        step_observations=[observation(player_x=300.0)]
    )
    env = StairAgentEnv(
        adapter,
        EnvironmentConfig(
            observation_history_frames=2,
            include_action_history=True,
        ),
    )
    env.reset()
    stepped, *_rest = env.step(2)
    assert stepped.reshape(2, 67)[-1, 64:].tolist() == [0.0, 0.0, 1.0]

    adapter.reset_observation = observation(player_x=250.0)
    reset_features, _info = env.reset()
    chunks = reset_features.reshape(2, 67)

    assert np.all(chunks[:, 64:] == 0.0)
    assert np.allclose(chunks[0], chunks[1])
    assert chunks[-1, 1] == pytest.approx(250 / 634)


def test_environment_can_disable_action_history() -> None:
    env = StairAgentEnv(
        FakeAdapter(),
        EnvironmentConfig(
            observation_history_frames=4,
            include_action_history=False,
        ),
    )

    features, _info = env.reset()

    assert features.shape == (256,)
    assert env.observation_space.contains(features)


def test_dialog_terminates_episode_and_releases_keys() -> None:
    adapter = FakeAdapter(
        step_observations=[observation(phase="dialog")]
    )
    env = StairAgentEnv(
        adapter,
        EnvironmentConfig(death_penalty=5.0, step_penalty=0.0),
    )
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
