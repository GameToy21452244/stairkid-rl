from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.calibration import FlippingCalibration
from stair_agent.simulator.scenarios import (
    configure_flipping_choice,
    configure_flipping_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def flipping_config(**changes) -> ShaftEnvConfig:
    return replace(
        ShaftEnvConfig(
            enable_flipping=True,
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
    raise AssertionError("固定 flipping 場景未落地。")


def test_flipping_cycle_configuration_is_validated() -> None:
    assert not ShaftEnvConfig().enable_flipping
    with pytest.raises(ValueError, match="active_seconds"):
        ShaftEnvConfig(flipping_active_seconds=0.0)
    with pytest.raises(ValueError, match="inactive_seconds"):
        ShaftEnvConfig(flipping_inactive_seconds=0.0)


def test_active_flipping_platform_accepts_landing_and_emits_event() -> None:
    env = ShaftEnv(config=flipping_config())
    try:
        env.reset(seed=1001)
        floor = configure_flipping_landing(
            env.simulator,
            active=True,
        )
        _observation, _reward, terminated, info = step_until_landing(env)
        assert not terminated
        assert env.simulator.last_landed_floor == floor
        assert "flipping_contact" in info["events"]
        assert info["environment_version"].endswith("+flipping-v1")
        assert info["flipping_enabled"]
        flipping = next(
            item
            for item in env.last_observation.platforms
            if item["kind"] == "flipping"
        )
        assert flipping["active"]
    finally:
        env.close()


def test_inactive_flipping_platform_does_not_collide() -> None:
    env = ShaftEnv(config=flipping_config())
    try:
        env.reset(seed=1002)
        floor = configure_flipping_landing(
            env.simulator,
            active=False,
        )
        all_events: list[str] = []
        for _ in range(5):
            _observation, _reward, _terminated, _truncated, info = env.step(0)
            all_events.extend(info["events"])
        assert "flipping_contact" not in all_events
        assert env.simulator.last_landed_floor != floor
    finally:
        env.close()


def test_flipping_platform_reactivates_after_full_cycle() -> None:
    env = ShaftEnv(config=flipping_config())
    try:
        env.reset(seed=1003)
        configure_flipping_landing(
            env.simulator,
            active=False,
        )
        platform = min(
            env.simulator.platforms,
            key=lambda item: item.floor_index,
        )
        assert not env.simulator.platform_is_active(platform)
        env.simulator.elapsed_seconds = (
            env.config.flipping_active_seconds
            + env.config.flipping_inactive_seconds
            + 0.01
        )
        assert env.simulator.platform_is_active(platform)
    finally:
        env.close()


def test_disabled_flipping_kind_behaves_as_normal_platform() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            enable_flipping=False,
            scroll_speed=0.0,
        )
    )
    try:
        env.reset(seed=1004)
        floor = configure_flipping_landing(
            env.simulator,
            active=False,
        )
        _observation, _reward, _terminated, info = step_until_landing(env)
        assert env.simulator.last_landed_floor == floor
        assert "flipping_contact" not in info["events"]
    finally:
        env.close()


def test_flipping_renderer_distinguishes_active_and_inactive() -> None:
    env = ShaftEnv(
        config=flipping_config(),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=1005)
        configure_flipping_landing(
            env.simulator,
            active=True,
        )
        active_frame = env.render()
        active_pixels = np.all(
            active_frame == (45, 190, 190), axis=2
        ).sum()
        configure_flipping_landing(
            env.simulator,
            active=False,
        )
        inactive_frame = env.render()
        inactive_pixels = np.all(
            inactive_frame == (70, 70, 82), axis=2
        ).sum()
        minimum = int(
            env.config.platform_width * env.config.platform_height
        )
        assert active_pixels >= minimum
        assert inactive_pixels >= minimum
    finally:
        env.close()


def test_oracle_prefers_normal_and_skips_inactive_flipping() -> None:
    env = ShaftEnv(config=flipping_config())
    try:
        env.reset(seed=1006)
        _flipping, safe = configure_flipping_choice(env.simulator)
        decision = OracleFull().choose(env.simulator)
        assert decision.target_platform_kind == "normal"
        assert decision.target_center_x == pytest.approx(safe.center_x)

        env.simulator.platforms.remove(safe)
        env.simulator.space.remove(safe.shape, safe.body)
        env.simulator.elapsed_seconds = (
            env.config.flipping_active_seconds + 0.05
        )
        inactive_decision = OracleFull().choose(env.simulator)
        assert inactive_decision.target_platform_id != (
            _flipping.floor_index
        )
    finally:
        env.close()


def test_flipping_calibration_applies_validated_cycle() -> None:
    calibrated = FlippingCalibration(
        active_seconds=1.25,
        inactive_seconds=0.75,
    ).apply(ShaftEnvConfig())
    assert calibrated.flipping_active_seconds == 1.25
    assert calibrated.flipping_inactive_seconds == 0.75


def test_enabling_flipping_without_flipping_platforms_has_no_effect() -> None:
    feature_off = ShaftEnv(config=ShaftEnvConfig())
    feature_on = ShaftEnv(config=ShaftEnvConfig(enable_flipping=True))
    actions = [0, 2, 2, 0, 1, 0] * 8
    try:
        feature_off.reset(seed=1007)
        feature_on.reset(seed=1007)
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
