from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.calibration import ConveyorCalibration
from stair_agent.simulator.scenarios import (
    configure_conveyor_choice,
    configure_conveyor_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def conveyor_config(**changes) -> ShaftEnvConfig:
    return replace(
        ShaftEnvConfig(
            enable_conveyor=True,
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
    raise AssertionError("固定 conveyor 場景未落地。")


@pytest.mark.parametrize(
    ("direction", "expected_delta", "direction_event"),
    [
        ("left", -80.0, "conveyor_left"),
        ("right", 80.0, "conveyor_right"),
    ],
)
def test_conveyor_landing_applies_directional_velocity_and_events(
    direction: str,
    expected_delta: float,
    direction_event: str,
) -> None:
    env = ShaftEnv(config=conveyor_config())
    try:
        env.reset(seed=801)
        configure_conveyor_landing(
            env.simulator,
            direction=direction,
        )
        _observation, _reward, terminated, info = step_until_landing(env)
        assert not terminated
        assert info["environment_version"].endswith("+conveyor-v1")
        assert info["conveyor_enabled"]
        assert info["conveyor_velocity_delta_x"] == pytest.approx(
            expected_delta
        )
        assert {"landed", "conveyor_contact", direction_event} <= set(
            info["events"]
        )
        assert env.simulator.player.body.velocity.x == pytest.approx(
            expected_delta
        )
        assert any(
            platform["kind"] == direction_event
            for platform in env.last_observation.platforms
        )
    finally:
        env.close()


def test_disabled_conveyor_platform_has_no_velocity_effect() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            enable_conveyor=False,
            scroll_speed=0.0,
        )
    )
    try:
        env.reset(seed=802)
        configure_conveyor_landing(
            env.simulator,
            direction="right",
        )
        _observation, _reward, _terminated, info = step_until_landing(env)
        assert info["conveyor_velocity_delta_x"] == 0.0
        assert "conveyor_contact" not in info["events"]
        assert env.simulator.player.body.velocity.x == pytest.approx(0.0)
    finally:
        env.close()


@pytest.mark.parametrize(
    ("direction", "color"),
    [
        ("left", (55, 145, 215)),
        ("right", (125, 85, 215)),
    ],
)
def test_conveyor_renderer_uses_direction_specific_color(
    direction: str,
    color: tuple[int, int, int],
) -> None:
    env = ShaftEnv(
        config=conveyor_config(),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=803)
        configure_conveyor_landing(
            env.simulator,
            direction=direction,
        )
        frame = env.render()
        color_pixels = np.all(frame == color, axis=2).sum()
        assert color_pixels >= int(
            env.config.platform_width * env.config.platform_height
        )
    finally:
        env.close()


def test_oracle_prefers_normal_alternative_over_conveyor_same_floor() -> None:
    env = ShaftEnv(config=conveyor_config())
    try:
        env.reset(seed=804)
        _conveyor, safe = configure_conveyor_choice(env.simulator)
        decision = OracleFull().choose(env.simulator)
        assert decision.target_platform_kind == "normal"
        assert decision.target_center_x == pytest.approx(safe.center_x)
    finally:
        env.close()


def test_conveyor_calibration_interface_applies_validated_velocity() -> None:
    calibrated = ConveyorCalibration(velocity_delta=72.0).apply(
        ShaftEnvConfig()
    )
    assert calibrated.conveyor_velocity_delta == 72.0
    with pytest.raises(ValueError, match="conveyor_velocity_delta"):
        replace(calibrated, conveyor_velocity_delta=0.0)


def test_invalid_conveyor_direction_is_rejected() -> None:
    env = ShaftEnv(config=conveyor_config())
    try:
        env.reset(seed=805)
        with pytest.raises(ValueError, match="left 或 right"):
            configure_conveyor_landing(
                env.simulator,
                direction="up",
            )
    finally:
        env.close()


def test_enabling_conveyor_without_conveyor_platforms_has_no_effect() -> None:
    feature_off = ShaftEnv(config=ShaftEnvConfig())
    feature_on = ShaftEnv(
        config=ShaftEnvConfig(enable_conveyor=True)
    )
    actions = [0, 2, 2, 0, 1, 0] * 8
    try:
        feature_off.reset(seed=806)
        feature_on.reset(seed=806)
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
