from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.calibration import HealthCalibration
from stair_agent.simulator.scenarios import configure_normal_healing_landing
from stair_agent.simulator.state import ShaftEnvConfig


def step_until_landing(env: ShaftEnv, *, use_oracle: bool = False):
    oracle = OracleFull()
    for _ in range(30):
        action = (
            int(oracle.choose(env.simulator).action) if use_oracle else 0
        )
        observation, reward, terminated, truncated, info = env.step(action)
        assert not terminated
        assert not truncated
        if "landed" in info["events"]:
            return observation, reward, info
    raise AssertionError("固定 normal-platform 場景未落地。")


def test_health_feature_is_disabled_by_default_and_does_not_heal() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(scroll_speed=0.0))
    try:
        env.reset(seed=601)
        configure_normal_healing_landing(
            env.simulator, health_segments=8
        )
        _observation, _reward, info = step_until_landing(env)
        assert not info["health_enabled"]
        assert info["health_segments"] == 8
        assert info["health_delta"] == 0
        assert "health_gained" not in info["events"]
    finally:
        env.close()


def test_normal_platform_heals_one_segment_and_updates_observation_reward() -> None:
    config = ShaftEnvConfig(
        enable_health=True,
        scroll_speed=0.0,
        health_gain_reward_per_segment=0.2,
    )
    env = ShaftEnv(config=config)
    try:
        env.reset(seed=602)
        configure_normal_healing_landing(
            env.simulator, health_segments=8
        )
        _observation, _reward, info = step_until_landing(env)
        assert info["health_segments"] == 9
        assert info["environment_version"].endswith("+health-v1")
        assert info["health_delta"] == 1
        assert "health_gained" in info["events"]
        assert info["reward_components"]["health_gain_reward"] == pytest.approx(
            0.2
        )
        assert env.last_observation.health == {
            "segments": 9,
            "delta": 1,
            "event": "increased",
        }
        gained = [
            event
            for event in env.last_observation.events
            if event["type"] == "health_gained"
        ]
        assert gained == [{"type": "health_gained", "health_delta": 1}]
    finally:
        env.close()


def test_normal_platform_healing_is_capped_and_emits_no_false_gain() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(enable_health=True, scroll_speed=0.0)
    )
    try:
        env.reset(seed=603)
        configure_normal_healing_landing(
            env.simulator, health_segments=12
        )
        _observation, _reward, info = step_until_landing(env)
        assert info["health_segments"] == 12
        assert info["health_delta"] == 0
        assert "health_gained" not in info["events"]
    finally:
        env.close()


def test_health_renderer_draws_filled_and_empty_segments() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(enable_health=True),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=604)
        env.simulator.health_segments = 5
        frame = env.render()
        filled = np.all(frame == (220, 55, 70), axis=2).sum()
        empty = np.all(frame == (65, 35, 40), axis=2).sum()
        assert filled == 5 * 8 * 8
        assert empty == 7 * 8 * 8
    finally:
        env.close()


def test_health_calibration_interface_applies_validated_parameters() -> None:
    calibrated = HealthCalibration(
        max_segments=10,
        initial_segments=7,
        normal_platform_heal_segments=2,
    ).apply(ShaftEnvConfig())
    assert calibrated.max_health_segments == 10
    assert calibrated.initial_health_segments == 7
    assert calibrated.normal_platform_heal_segments == 2
    with pytest.raises(ValueError, match="max_health_segments"):
        replace(calibrated, max_health_segments=0)


def test_oracle_remains_compatible_with_health_landing_scenario() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(enable_health=True, scroll_speed=0.0)
    )
    try:
        env.reset(seed=605)
        configure_normal_healing_landing(
            env.simulator, health_segments=6
        )
        _observation, _reward, info = step_until_landing(
            env, use_oracle=True
        )
        assert info["health_segments"] == 7
        assert "health_gained" in info["events"]
    finally:
        env.close()


def test_enabling_full_health_does_not_change_normal_platform_physics() -> None:
    disabled = ShaftEnv(config=ShaftEnvConfig(enable_health=False))
    enabled = ShaftEnv(config=ShaftEnvConfig(enable_health=True))
    actions = [0, 2, 2, 0, 1, 0] * 8
    try:
        disabled.reset(seed=606)
        enabled.reset(seed=606)
        for action in actions:
            disabled.step(action)
            enabled.step(action)
            np.testing.assert_allclose(
                disabled.simulator.player.body.position,
                enabled.simulator.player.body.position,
            )
            np.testing.assert_allclose(
                disabled.simulator.player.body.velocity,
                enabled.simulator.player.body.velocity,
            )
            assert [
                (item.floor_index, item.center_x, item.center_y)
                for item in disabled.simulator.platforms
            ] == [
                (item.floor_index, item.center_x, item.center_y)
                for item in enabled.simulator.platforms
            ]
    finally:
        disabled.close()
        enabled.close()
