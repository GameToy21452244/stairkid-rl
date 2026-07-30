from __future__ import annotations

import numpy as np
import pymunk

from ..input_controller import Action
from .generator import generate_platforms
from .platform import SimulatorPlatform
from .player import SimulatorPlayer
from .state import ShaftEnvConfig, SimulatorStep


class ShaftSimulator:
    """Small deterministic physics core; it never imports Windows input code."""

    def __init__(
        self,
        config: ShaftEnvConfig,
        rng: np.random.Generator,
    ) -> None:
        self.config = config
        self.rng = rng
        self.space = pymunk.Space()
        self.space.gravity = (0.0, config.gravity)
        self.platforms = generate_platforms(config, rng)
        first = self.platforms[0]
        self.player = SimulatorPlayer(
            width=config.player_width,
            height=config.player_height,
            position=(
                first.center_x,
                first.top + config.player_height / 2,
            ),
        )
        self.space.add(self.player.body, self.player.shape)
        for platform in self.platforms:
            self.space.add(platform.body, platform.shape)
        self.deepest_floor = 0
        self.last_landed_floor: int | None = None

    def _apply_horizontal_action(self, action: Action) -> None:
        velocity = self.player.body.velocity
        velocity_x = float(velocity.x)
        if action is Action.LEFT:
            velocity_x -= self.config.horizontal_acceleration * self.config.dt
        elif action is Action.RIGHT:
            velocity_x += self.config.horizontal_acceleration * self.config.dt
        else:
            velocity_x *= self.config.release_drag
            if abs(velocity_x) < 0.5:
                velocity_x = 0.0
        velocity_x = float(
            np.clip(
                velocity_x,
                -self.config.max_horizontal_speed,
                self.config.max_horizontal_speed,
            )
        )
        self.player.body.velocity = (velocity_x, velocity.y)

    def _move_platforms(self) -> None:
        if not self.config.scroll_speed:
            return
        shift = self.config.scroll_speed * self.config.dt
        for platform in self.platforms:
            platform.body.position = (
                platform.body.position.x,
                platform.body.position.y + shift,
            )

    def _landing_platform(
        self,
        previous_bottom: float,
        current_bottom: float,
    ) -> SimulatorPlatform | None:
        if self.player.body.velocity.y > 0:
            return None
        player_left = self.player.body.position.x - self.player.width / 2
        player_right = self.player.body.position.x + self.player.width / 2
        candidates = []
        for platform in self.platforms:
            if player_right <= platform.left or player_left >= platform.right:
                continue
            if (
                previous_bottom >= platform.top - 1.5
                and current_bottom <= platform.top
            ):
                candidates.append(platform)
        if not candidates:
            return None
        return max(candidates, key=lambda platform: platform.top)

    def _clamp_horizontal_bounds(self) -> None:
        half_width = self.player.width / 2
        x = float(
            np.clip(
                self.player.body.position.x,
                half_width,
                self.config.width - half_width,
            )
        )
        if x != self.player.body.position.x:
            self.player.body.position = (x, self.player.body.position.y)
            self.player.body.velocity = (0.0, self.player.body.velocity.y)

    def step(self, action: Action) -> SimulatorStep:
        self._apply_horizontal_action(action)
        self._move_platforms()
        previous_bottom = (
            self.player.body.position.y - self.player.height / 2
        )
        self.space.step(self.config.dt)
        self._clamp_horizontal_bounds()
        current_bottom = (
            self.player.body.position.y - self.player.height / 2
        )
        events: list[str] = []
        platform = self._landing_platform(previous_bottom, current_bottom)
        if platform is not None:
            self.player.body.position = (
                self.player.body.position.x,
                platform.top + self.player.height / 2,
            )
            self.player.body.velocity = (
                self.player.body.velocity.x,
                self.config.jump_velocity,
            )
            events.append("landed")
            self.last_landed_floor = platform.floor_index
            if platform.floor_index > self.deepest_floor:
                self.deepest_floor = platform.floor_index
                events.append("floor_descended")

        terminal_reason = None
        if self.player.body.position.y + self.player.height / 2 < 0:
            terminal_reason = "bottom"
        elif (
            self.player.body.position.y - self.player.height / 2
            > self.config.height
        ):
            terminal_reason = "top"
        return SimulatorStep(
            events=tuple(events),
            terminated=terminal_reason is not None,
            terminal_reason=terminal_reason,
        )
