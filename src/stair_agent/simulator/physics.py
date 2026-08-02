from __future__ import annotations

import numpy as np
import pymunk

from ..input_controller import Action
from .generator import (
    generate_platforms,
    next_platform_center,
    next_platform_kind,
)
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
        self._physics_substep_accumulator = 0.0
        self.health_segments = config.initial_health_segments
        self.last_health_delta = 0
        self.last_conveyor_velocity_delta_x = 0.0
        self.last_spring_velocity_delta_y = 0.0
        self.elapsed_seconds = 0.0

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

    def _move_platforms(self, dt: float) -> None:
        if not self.config.scroll_speed:
            return
        shift = self.config.scroll_speed * dt
        for platform in self.platforms:
            platform.body.position = (
                platform.body.position.x,
                platform.body.position.y + shift,
            )

    def _recycle_platforms(self) -> None:
        threshold = self.config.height + self.config.recycle_margin
        while self.platforms and max(p.top for p in self.platforms) > threshold:
            highest = max(self.platforms, key=lambda item: item.center_y)
            lowest = min(self.platforms, key=lambda item: item.center_y)
            self.space.remove(highest.shape, highest.body)
            self.platforms.remove(highest)
            replacement_floor = max(
                [item.floor_index for item in self.platforms]
                + [highest.floor_index]
            ) + 1
            ordered_kinds = [
                item.kind
                for item in sorted(
                    self.platforms,
                    key=lambda item: item.floor_index,
                )
            ]
            replacement = SimulatorPlatform.create(
                floor_index=replacement_floor,
                center_x=next_platform_center(
                    self.config, self.rng, lowest.center_x
                ),
                center_y=lowest.center_y - self.config.platform_spacing,
                width=self.config.platform_width,
                height=self.config.platform_height,
                kind=next_platform_kind(
                    self.config,
                    self.rng,
                    floor_index=replacement_floor,
                    previous_kinds=ordered_kinds,
                ),
            )
            self.platforms.append(replacement)
            self.space.add(replacement.body, replacement.shape)

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
            if not self.platform_is_active(platform):
                continue
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

    def platform_is_active(
        self,
        platform: SimulatorPlatform,
    ) -> bool:
        if (
            not self.config.enable_flipping
            or platform.kind != "flipping"
        ):
            return True
        cycle = (
            self.config.flipping_active_seconds
            + self.config.flipping_inactive_seconds
        )
        phase = self.elapsed_seconds % cycle
        return phase < self.config.flipping_active_seconds

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
        events: list[str] = []
        self.last_health_delta = 0
        self.last_conveyor_velocity_delta_x = 0.0
        self.last_spring_velocity_delta_y = 0.0
        self._physics_substep_accumulator += (
            self.config.physics_hz / self.config.fps
        )
        substeps = int(self._physics_substep_accumulator)
        self._physics_substep_accumulator -= substeps
        for _ in range(substeps):
            self.elapsed_seconds += self.config.physics_dt
            self._move_platforms(self.config.physics_dt)
            previous_bottom = (
                self.player.body.position.y - self.player.height / 2
            )
            self.space.step(self.config.physics_dt)
            self._clamp_horizontal_bounds()
            current_bottom = (
                self.player.body.position.y - self.player.height / 2
            )
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
                if "landed" not in events:
                    events.append("landed")
                self.last_landed_floor = platform.floor_index
                if platform.floor_index > self.deepest_floor:
                    self.deepest_floor = platform.floor_index
                    events.append("floor_descended")
                if (
                    self.config.enable_spikes
                    and platform.kind == "spikes"
                ):
                    previous_health = self.health_segments
                    self.health_segments = max(
                        0,
                        self.health_segments
                        - self.config.spike_damage_segments,
                    )
                    self.last_health_delta = (
                        self.health_segments - previous_health
                    )
                    events.append("spike_contact")
                    if self.last_health_delta < 0:
                        events.append("damage")
                    if self.health_segments <= 0:
                        events.append("health_depleted")
                elif (
                    self.config.enable_conveyor
                    and platform.kind
                    in {"conveyor_left", "conveyor_right"}
                ):
                    direction = (
                        -1.0
                        if platform.kind == "conveyor_left"
                        else 1.0
                    )
                    previous_velocity_x = float(
                        self.player.body.velocity.x
                    )
                    next_velocity_x = float(
                        np.clip(
                            previous_velocity_x
                            + direction
                            * self.config.conveyor_velocity_delta,
                            -self.config.max_horizontal_speed,
                            self.config.max_horizontal_speed,
                        )
                    )
                    self.player.body.velocity = (
                        next_velocity_x,
                        self.player.body.velocity.y,
                    )
                    self.last_conveyor_velocity_delta_x = (
                        next_velocity_x - previous_velocity_x
                    )
                    events.extend(
                        ("conveyor_contact", platform.kind)
                    )
                elif (
                    self.config.enable_spring
                    and platform.kind == "spring"
                ):
                    self.last_spring_velocity_delta_y = (
                        self.config.spring_jump_velocity
                        - float(self.player.body.velocity.y)
                    )
                    self.player.body.velocity = (
                        self.player.body.velocity.x,
                        self.config.spring_jump_velocity,
                    )
                    events.extend(("spring_contact", "spring_bounce"))
                elif (
                    self.config.enable_flipping
                    and platform.kind == "flipping"
                ):
                    events.append("flipping_contact")
                elif (
                    self.config.enable_health
                    and platform.kind == "normal"
                ):
                    previous_health = self.health_segments
                    self.health_segments = min(
                        self.config.max_health_segments,
                        self.health_segments
                        + self.config.normal_platform_heal_segments,
                    )
                    self.last_health_delta = (
                        self.health_segments - previous_health
                    )
                    if self.last_health_delta > 0:
                        events.append("health_gained")
            self._recycle_platforms()

        terminal_reason = None
        if self.config.enable_health and self.health_segments <= 0:
            terminal_reason = "health_depleted"
        elif self.player.body.position.y + self.player.height / 2 < 0:
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
            health_delta=self.last_health_delta,
            conveyor_velocity_delta_x=(
                self.last_conveyor_velocity_delta_x
            ),
            spring_velocity_delta_y=self.last_spring_velocity_delta_y,
        )
