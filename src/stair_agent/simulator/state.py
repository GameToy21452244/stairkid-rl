from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShaftEnvConfig:
    width: int = 634
    height: int = 431
    # One simulator action corresponds to the measured 125 ms control step.
    fps: int = 8
    max_episode_steps: int = 3000
    player_width: float = 24.0
    player_height: float = 27.0
    horizontal_acceleration: float = 1048.0
    max_horizontal_speed: float = 230.0
    release_drag: float = 0.035
    gravity: float = -192.0
    jump_velocity: float = 95.0
    platform_width: float = 96.0
    platform_height: float = 16.0
    platform_spacing: float = 48.0
    max_platform_shift: float = 180.0
    platform_count: int = 9
    scroll_speed: float = 96.0
    step_penalty: float = 0.01
    landing_reward: float = 0.05
    floor_reward: float = 1.0
    death_penalty: float = 5.0
    observation_history_frames: int = 4
    include_action_history: bool = True

    @property
    def dt(self) -> float:
        return 1.0 / self.fps


@dataclass(frozen=True)
class SimulatorStep:
    events: tuple[str, ...]
    terminated: bool
    terminal_reason: str | None
