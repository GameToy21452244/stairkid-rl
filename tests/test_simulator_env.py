from __future__ import annotations

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.envs.shaft_env import ShaftEnv, ShaftEnvConfig
from stair_agent.input_controller import Action
from stair_agent.simulator.generator import sequence_is_reachable


def test_simulator_passes_gymnasium_check_env() -> None:
    env = ShaftEnv()
    try:
        check_env(env, skip_render_check=True)
    finally:
        env.close()


def test_simulator_uses_real_compatible_observation_schema() -> None:
    env = ShaftEnv()
    try:
        observation, info = env.reset(seed=11)
        assert observation.shape == (268,)
        assert observation.dtype == np.float32
        assert env.observation_space.contains(observation)
        assert info["raw_feature_count"] == 64
        assert info["stacked_feature_count"] == 268
        assert info["observation_schema_version"] == "stair-observation-v3-268"
    finally:
        env.close()


def test_fixed_seed_produces_identical_initial_state() -> None:
    first = ShaftEnv()
    second = ShaftEnv()
    try:
        first_observation, first_info = first.reset(seed=42)
        second_observation, second_info = second.reset(seed=42)
        np.testing.assert_array_equal(first_observation, second_observation)
        assert first_info["platforms"] == second_info["platforms"]
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize("fps", [8, 10, 12])
def test_v02_uses_fixed_60hz_physics_with_supported_policy_rates(fps: int) -> None:
    env = ShaftEnv(config=ShaftEnvConfig(fps=fps))
    try:
        _observation, info = env.reset(seed=420)
        assert info["environment_version"] == "ns-shaft-sim-v0.2"
        assert info["physics_frequency_hz"] == 60
        assert info["control_frequency_hz"] == fps
    finally:
        env.close()


def test_easy_platform_sequence_has_three_floor_safe_reachability() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    try:
        env.reset(seed=421)
        assert sequence_is_reachable(env.config, env.simulator.platforms)
    finally:
        env.close()


def test_platforms_recycle_continuously_and_reproducibly() -> None:
    config = ShaftEnvConfig(
        distribution="easy",
        scroll_speed=480.0,
        max_episode_steps=200,
    )
    first = ShaftEnv(config=config)
    second = ShaftEnv(config=config)
    try:
        first.reset(seed=422)
        second.reset(seed=422)
        initial_max_floor = max(p.floor_index for p in first.simulator.platforms)
        for _ in range(20):
            first.step(0)
            second.step(0)
        assert max(p.floor_index for p in first.simulator.platforms) > initial_max_floor
        first_state = [
            (p.floor_index, p.center_x, p.center_y)
            for p in sorted(first.simulator.platforms, key=lambda item: item.floor_index)
        ]
        second_state = [
            (p.floor_index, p.center_x, p.center_y)
            for p in sorted(second.simulator.platforms, key=lambda item: item.floor_index)
        ]
        assert first_state == second_state
        assert len(first_state) == config.platform_count
    finally:
        first.close()
        second.close()


def test_gravity_horizontal_acceleration_and_release_drag() -> None:
    config = ShaftEnvConfig(scroll_speed=0.0)
    env = ShaftEnv(config=config)
    try:
        env.reset(seed=1)
        body = env.simulator.player.body
        body.position = (config.width / 2, config.height - 40)
        body.velocity = (0.0, 0.0)
        env.step(int(Action.RIGHT))
        assert body.velocity.x > 0.0
        assert body.velocity.y < 0.0

        speed_before_release = abs(body.velocity.x)
        env.step(int(Action.RELEASE_ALL))
        assert abs(body.velocity.x) < speed_before_release
    finally:
        env.close()


def test_one_way_platform_landing_bounces_from_above() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(scroll_speed=0.0))
    try:
        env.reset(seed=3)
        platform = env.simulator.platforms[0]
        body = env.simulator.player.body
        body.position = (
            platform.center_x,
            platform.top + env.simulator.player.height / 2 + 18,
        )
        body.velocity = (0.0, -180.0)

        landed = False
        for _ in range(30):
            _obs, _reward, terminated, _truncated, info = env.step(0)
            assert not terminated
            if "landed" in info["events"]:
                landed = True
                break

        assert landed
        assert body.velocity.y > 0
        assert body.position.y >= (
            platform.top + env.simulator.player.height / 2
        )
    finally:
        env.close()


def test_horizontal_bounds_and_bottom_death() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(scroll_speed=0.0))
    try:
        env.reset(seed=4)
        body = env.simulator.player.body
        body.position = (1.0, 150.0)
        body.velocity = (-500.0, 0.0)
        _obs, _reward, terminated, _truncated, info = env.step(1)
        assert not terminated
        assert body.position.x >= env.simulator.player.width / 2
        assert info["terminal_reason"] is None

        body.position = (100.0, -100.0)
        _obs, _reward, terminated, truncated, info = env.step(0)
        assert terminated
        assert not truncated
        assert info["terminal_reason"] == "bottom"
        assert info["reward_components"]["death_penalty"] < 0
    finally:
        env.close()


def test_time_limit_is_truncated_not_terminated() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(max_episode_steps=1, scroll_speed=0.0)
    )
    try:
        env.reset(seed=5)
        _obs, _reward, terminated, truncated, info = env.step(0)
        assert not terminated
        assert truncated
        assert info["terminal_reason"] == "time_limit"
    finally:
        env.close()


def test_invalid_action_is_rejected() -> None:
    env = ShaftEnv()
    try:
        env.reset(seed=6)
        with pytest.raises(ValueError, match="無效動作"):
            env.step(3)
    finally:
        env.close()


def test_rgb_array_render_is_headless_and_has_expected_shape() -> None:
    env = ShaftEnv(render_mode="rgb_array")
    try:
        env.reset(seed=7)
        frame = env.render()
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (env.config.height, env.config.width, 3)
        assert frame.dtype == np.uint8
        env.step(2)
        frame_with_overlay = env.render()
        assert not np.array_equal(frame, frame_with_overlay)
    finally:
        env.close()


def test_none_render_mode_does_not_allocate_a_frame() -> None:
    env = ShaftEnv()
    try:
        env.reset(seed=70)
        assert env.render() is None
    finally:
        env.close()


def test_existing_baseline_can_drive_simulator_observations() -> None:
    env = ShaftEnv()
    policy = SafePlatformPolicy(BaselineConfig())
    try:
        env.reset(seed=8)
        for _ in range(200):
            decision = policy.choose(env.last_observation)
            assert env.action_space.contains(int(decision.action))
            _obs, _reward, terminated, truncated, _info = env.step(
                int(decision.action)
            )
            if terminated or truncated:
                env.reset()
                policy.reset()
    finally:
        env.close()


def test_floor_descended_event_is_unique_and_matches_deepest_floor() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            distribution="easy",
            fps=10,
            max_episode_steps=300,
        )
    )
    policy = SafePlatformPolicy(BaselineConfig())
    floor_events = 0
    previous_deepest = 0
    try:
        env.reset(seed=81)
        for _ in range(300):
            decision = policy.choose(env.last_observation)
            _obs, _reward, terminated, truncated, info = env.step(
                int(decision.action)
            )
            descended = "floor_descended" in info["events"]
            floor_events += int(descended)
            if descended:
                assert env.simulator.deepest_floor > previous_deepest
            else:
                assert env.simulator.deepest_floor == previous_deepest
            assert floor_events <= env.simulator.deepest_floor
            previous_deepest = env.simulator.deepest_floor
            if terminated or truncated:
                break
        assert floor_events > 0
    finally:
        env.close()


def test_simulator_100k_step_headless_smoke() -> None:
    env = ShaftEnv()
    rng = np.random.default_rng(123)
    try:
        env.reset(seed=123)
        for _ in range(100_000):
            _obs, _reward, terminated, truncated, _info = env.step(
                int(rng.integers(0, 3))
            )
            if terminated or truncated:
                env.reset()
    finally:
        env.close()
