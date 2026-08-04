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
from stair_agent.training.spring_curriculum_gate import spring_curriculum_config


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


def test_oracle_spring_clearance_escapes_aligned_source_before_targeting() -> None:
    env = ShaftEnv(config=spring_config())
    try:
        env.reset(seed=906)
        source = min(env.simulator.platforms, key=lambda item: item.floor_index)
        target = min(
            (
                item
                for item in env.simulator.platforms
                if item.floor_index > source.floor_index
            ),
            key=lambda item: item.floor_index,
        )
        source.kind = "spring"
        target.kind = "normal"
        target.body.position = (source.center_x, target.center_y)
        env.simulator.deepest_floor = source.floor_index
        env.simulator.last_landed_floor = source.floor_index
        env.simulator.player.body.position = (
            source.center_x,
            source.top + env.config.player_height / 2 + 24,
        )
        env.simulator.player.body.velocity = (0.0, 150.0)

        legacy = OracleFull(enable_spring_escape=False).choose(env.simulator)
        candidate = OracleFull(enable_spring_escape=True).choose(env.simulator)
        assert legacy.action.value == 0
        assert candidate.action.value in {1, 2}

        direction = -1 if candidate.action.value == 1 else 1
        clear_x = (
            source.center_x
            + direction
            * (
                source.width / 2
                + env.config.player_width / 2
                + 3
            )
        )
        env.simulator.player.body.position = (
            clear_x,
            env.simulator.player.body.position.y,
        )
        cleared = OracleFull(enable_spring_escape=True).choose(env.simulator)
        assert cleared.action.value == 0
    finally:
        env.close()


def test_oracle_spring_escape_repairs_frozen_failure_seed() -> None:
    def rollout(enabled: bool) -> tuple[int, str | None]:
        env = ShaftEnv(
            config=replace(
                spring_curriculum_config(),
                environment_version="ns-shaft-sim-v0.2",
                enable_support_ownership=False,
                enable_calibrated_playfield=False,
            )
        )
        oracle = OracleFull(enable_spring_escape=enabled)
        env.reset(seed=10007)
        terminal = None
        try:
            for _ in range(120):
                decision = oracle.choose(env.simulator)
                _, _, terminated, truncated, info = env.step(
                    int(decision.action)
                )
                if env.simulator.deepest_floor >= 10:
                    terminal = "target_reached"
                    break
                if terminated or truncated:
                    terminal = info["terminal_reason"]
                    break
            return env.simulator.deepest_floor, terminal
        finally:
            env.close()

    legacy = rollout(False)
    candidate = rollout(True)
    assert legacy == (4, "top")
    assert candidate == (10, "target_reached")
