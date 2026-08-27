from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.simulator.scenarios import configure_flipping_landing
from stair_agent.simulator.state import ShaftEnvConfig


def flipping_config(**changes) -> ShaftEnvConfig:
    return replace(
        ShaftEnvConfig(enable_flipping=True, scroll_speed=0.0),
        **changes,
    )


@pytest.mark.parametrize("fps", [8, 10, 12, 60])
def test_corrected_flipping_state_machine_is_control_cadence_invariant(fps: int) -> None:
    config_changes = {"fps": fps}
    if fps == 60:
        config_changes["allow_manual_60hz_control"] = True
    env = ShaftEnv(config=flipping_config(**config_changes))
    try:
        env.reset(seed=1003)
        configure_flipping_landing(env.simulator, active=True)
        platform = min(env.simulator.platforms, key=lambda item: item.floor_index)
        state = env.simulator.flipping_states[platform.floor_index]
        assert state == {"state": "READY", "elapsed": 0.0}
        assert env.simulator.platform_is_active(platform)

        env.simulator.trigger_flipping_platform(platform.floor_index)
        assert state == {"state": "TRIGGERED", "elapsed": 0.0}
        assert env.simulator.platform_is_active(platform)

        active_ticks = round(config_changes.get("physics_hz", env.config.physics_hz) * env.config.flipping_active_seconds)
        for _ in range(active_ticks):
            env.simulator._update_flipping_states(env.config.physics_dt)
        assert state == {"state": "INACTIVE", "elapsed": 0.0}
        assert not env.simulator.platform_is_active(platform)

        env.simulator.elapsed_seconds = 100.0
        assert not env.simulator.platform_is_active(platform)
        inactive_ticks = round(env.config.physics_hz * env.config.flipping_inactive_seconds)
        for _ in range(inactive_ticks - 1):
            env.simulator._update_flipping_states(env.config.physics_dt)
        assert state["state"] == "INACTIVE"
        assert not env.simulator.platform_is_active(platform)
        env.simulator._update_flipping_states(env.config.physics_dt)
        assert state == {"state": "READY", "elapsed": 0.0}
        assert env.simulator.platform_is_active(platform)
    finally:
        env.close()


@pytest.mark.parametrize("episode_elapsed", [2.0, 10.0, 100.0])
def test_global_elapsed_never_overrides_explicit_inactive_state(
    episode_elapsed: float,
) -> None:
    env = ShaftEnv(config=flipping_config())
    try:
        env.reset(seed=1004)
        configure_flipping_landing(env.simulator, active=False)
        platform = min(env.simulator.platforms, key=lambda item: item.floor_index)
        env.simulator.elapsed_seconds = episode_elapsed
        assert not env.simulator.platform_is_active(platform)
    finally:
        env.close()


def test_inactive_flipping_is_noncollidable_and_renderer_uses_inactive_color() -> None:
    env = ShaftEnv(config=flipping_config(), render_mode="rgb_array")
    try:
        env.reset(seed=1005)
        floor = configure_flipping_landing(env.simulator, active=False)
        env.simulator.elapsed_seconds = 100.0
        events: list[str] = []
        for _ in range(5):
            _, _, _, _, info = env.step(0)
            events.extend(info["events"])
        assert "flipping_contact" not in events
        assert env.simulator.last_landed_floor != floor
        frame = env.render()
        inactive_pixels = np.all(frame == (70, 70, 82), axis=2).sum()
        assert inactive_pixels >= int(env.config.platform_width * env.config.platform_height)
    finally:
        env.close()
