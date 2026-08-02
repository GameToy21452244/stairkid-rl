from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.calibration import SpikeCalibration
from stair_agent.simulator.scenarios import (
    configure_spike_choice,
    configure_spike_landing,
)
from stair_agent.simulator.state import ShaftEnvConfig


def step_until_landing(env: ShaftEnv):
    for _ in range(30):
        observation, reward, terminated, truncated, info = env.step(0)
        assert not truncated
        if "landed" in info["events"]:
            return observation, reward, terminated, info
    raise AssertionError("固定 spike 場景未落地。")


def spike_config(**changes) -> ShaftEnvConfig:
    return replace(
        ShaftEnvConfig(
            enable_health=True,
            enable_spikes=True,
            scroll_speed=0.0,
        ),
        **changes,
    )


def test_spikes_require_health_and_are_disabled_by_default() -> None:
    assert not ShaftEnvConfig().enable_spikes
    with pytest.raises(ValueError, match="需要 enable_health"):
        ShaftEnvConfig(enable_spikes=True)


def test_spike_landing_deals_five_damage_and_emits_auditable_events() -> None:
    env = ShaftEnv(
        config=spike_config(spike_damage_penalty_per_segment=0.1)
    )
    try:
        env.reset(seed=701)
        configure_spike_landing(env.simulator, health_segments=12)
        _observation, _reward, terminated, info = step_until_landing(env)
        assert not terminated
        assert info["environment_version"].endswith(
            "+health-v1+spikes-v1"
        )
        assert info["health_segments"] == 7
        assert info["health_delta"] == -5
        assert {"landed", "spike_contact", "damage"} <= set(info["events"])
        assert "health_gained" not in info["events"]
        assert info["reward_components"]["damage_penalty"] == pytest.approx(
            -0.5
        )
        assert env.last_observation.health == {
            "segments": 7,
            "delta": -5,
            "event": "decreased",
        }
        damage = [
            event
            for event in env.last_observation.events
            if event["type"] == "damage"
        ]
        assert damage == [{"type": "damage", "health_delta": -5}]
        assert any(
            platform["kind"] == "spikes"
            for platform in env.last_observation.platforms
        )
    finally:
        env.close()


def test_lethal_spike_terminates_with_health_depleted_reason() -> None:
    env = ShaftEnv(config=spike_config())
    try:
        env.reset(seed=702)
        configure_spike_landing(env.simulator, health_segments=5)
        _observation, _reward, terminated, info = step_until_landing(env)
        assert terminated
        assert info["health_segments"] == 0
        assert info["terminal_reason"] == "health_depleted"
        assert info["failure_reason"] == "health_depleted"
        assert "health_depleted" in info["events"]
        assert info["reward_components"]["death_penalty"] < 0
    finally:
        env.close()


def test_disabled_spike_mechanism_does_not_apply_damage() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            enable_health=True,
            enable_spikes=False,
            scroll_speed=0.0,
        )
    )
    try:
        env.reset(seed=703)
        configure_spike_landing(env.simulator, health_segments=9)
        _observation, _reward, terminated, info = step_until_landing(env)
        assert not terminated
        assert info["health_segments"] == 9
        assert info["health_delta"] == 0
        assert "damage" not in info["events"]
    finally:
        env.close()


def test_spike_renderer_uses_distinct_red_platform_color() -> None:
    env = ShaftEnv(
        config=spike_config(),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=704)
        configure_spike_landing(env.simulator, health_segments=12)
        frame = env.render()
        red_pixels = np.all(frame == (205, 55, 65), axis=2).sum()
        assert red_pixels >= int(
            env.config.platform_width * env.config.platform_height
        )
    finally:
        env.close()


def test_oracle_prefers_normal_alternative_over_spike_same_floor() -> None:
    env = ShaftEnv(config=spike_config())
    try:
        env.reset(seed=705)
        _spike, safe = configure_spike_choice(env.simulator)
        decision = OracleFull().choose(env.simulator)
        assert decision.target_platform_kind == "normal"
        assert decision.target_center_x == pytest.approx(safe.center_x)
    finally:
        env.close()


def test_spike_calibration_interface_applies_validated_damage() -> None:
    calibrated = SpikeCalibration(damage_segments=4).apply(
        ShaftEnvConfig()
    )
    assert calibrated.spike_damage_segments == 4
    with pytest.raises(ValueError, match="spike_damage_segments"):
        replace(calibrated, spike_damage_segments=0)


def test_enabling_spikes_without_spike_platforms_has_no_physics_effect() -> None:
    health_only = ShaftEnv(
        config=ShaftEnvConfig(enable_health=True, enable_spikes=False)
    )
    spikes_enabled = ShaftEnv(config=spike_config(scroll_speed=96.0))
    actions = [0, 2, 2, 0, 1, 0] * 8
    try:
        health_only.reset(seed=706)
        spikes_enabled.reset(seed=706)
        for action in actions:
            health_only.step(action)
            spikes_enabled.step(action)
            np.testing.assert_allclose(
                health_only.simulator.player.body.position,
                spikes_enabled.simulator.player.body.position,
            )
            np.testing.assert_allclose(
                health_only.simulator.player.body.velocity,
                spikes_enabled.simulator.player.body.velocity,
            )
            assert health_only.simulator.health_segments == (
                spikes_enabled.simulator.health_segments
            )
    finally:
        health_only.close()
        spikes_enabled.close()
