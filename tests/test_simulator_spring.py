from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.calibration import SpringCalibration
from stair_agent.simulator.scenarios import (
    configure_spring_choice,
    configure_spring_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def spring_config(**changes) -> ShaftEnvConfig:
    return replace(
        ShaftEnvConfig(
            enable_spring=True,
            scroll_speed=0.0,
        ),
        **changes,
    )


def step_until_landing(env: ShaftEnv):
    for _ in range(30):
        observation, reward, terminated, truncated, info = env.step(0)
        assert not truncated
        if "landed" in info["events"]:
            return observation, reward, terminated, info
    raise AssertionError("固定 spring 場景未落地。")


def test_spring_landing_applies_stronger_bounce_and_events() -> None:
    env = ShaftEnv(config=spring_config())
    try:
        env.reset(seed=901)
        configure_spring_landing(env.simulator)
        _observation, _reward, terminated, info = step_until_landing(env)
        assert not terminated
        assert info["environment_version"].endswith("+spring-v1")
        assert info["spring_enabled"]
        assert info["spring_velocity_delta_y"] == pytest.approx(95.0)
        assert {"landed", "spring_contact", "spring_bounce"} <= set(
            info["events"]
        )
        assert env.simulator.player.body.velocity.y > (
            env.config.jump_velocity
        )
        assert any(
            platform["kind"] == "spring"
            for platform in env.last_observation.platforms
        )
    finally:
        env.close()


def test_disabled_spring_platform_uses_normal_bounce() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            enable_spring=False,
            scroll_speed=0.0,
        )
    )
    try:
        env.reset(seed=902)
        configure_spring_landing(env.simulator)
        _observation, _reward, _terminated, info = step_until_landing(env)
        assert info["spring_velocity_delta_y"] == 0.0
        assert "spring_contact" not in info["events"]
        assert env.simulator.player.body.velocity.y <= (
            env.config.jump_velocity
        )
    finally:
        env.close()


def test_spring_renderer_uses_distinct_orange_color() -> None:
    env = ShaftEnv(
        config=spring_config(),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=903)
        configure_spring_landing(env.simulator)
        frame = env.render()
        orange_pixels = np.all(frame == (235, 155, 45), axis=2).sum()
        assert orange_pixels >= int(
            env.config.platform_width * env.config.platform_height
        )
    finally:
        env.close()


def test_oracle_prefers_normal_alternative_over_spring_same_floor() -> None:
    env = ShaftEnv(config=spring_config())
    try:
        env.reset(seed=904)
        _spring, safe = configure_spring_choice(env.simulator)
        decision = OracleFull().choose(env.simulator)
        assert decision.target_platform_kind == "normal"
        assert decision.target_center_x == pytest.approx(safe.center_x)
    finally:
        env.close()


def test_spring_calibration_requires_stronger_than_normal_bounce() -> None:
    calibrated = SpringCalibration(jump_velocity=175.0).apply(
        ShaftEnvConfig()
    )
    assert calibrated.spring_jump_velocity == 175.0
    with pytest.raises(ValueError, match="大於一般 jump_velocity"):
        replace(calibrated, spring_jump_velocity=90.0)


def test_enabling_spring_without_spring_platforms_has_no_effect() -> None:
    feature_off = ShaftEnv(config=ShaftEnvConfig())
    feature_on = ShaftEnv(config=ShaftEnvConfig(enable_spring=True))
    actions = [0, 2, 2, 0, 1, 0] * 8
    try:
        feature_off.reset(seed=905)
        feature_on.reset(seed=905)
        for action in actions:
            feature_off.step(action)
            feature_on.step(action)
            np.testing.assert_allclose(
                feature_off.simulator.player.body.position,
                feature_on.simulator.player.body.position,
            )
            np.testing.assert_allclose(
                feature_off.simulator.player.body.velocity,
                feature_on.simulator.player.body.velocity,
            )
    finally:
        feature_off.close()
        feature_on.close()
