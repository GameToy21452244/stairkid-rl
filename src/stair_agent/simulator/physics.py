from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

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
from .state import ShaftEnvConfig, SimulatorStep, SupportDepartureRecord


@dataclass(frozen=True)
class PlatformSnapshot:
    floor_index: int
    center_x: float
    center_y: float
    kind: str


@dataclass(frozen=True)
class SimulatorSnapshot:
    player_position: tuple[float, float]
    player_velocity: tuple[float, float]
    player_angle: float
    player_angular_velocity: float
    player_force: tuple[float, float]
    player_torque: float
    platforms: tuple[PlatformSnapshot, ...]
    platform_objects: tuple[SimulatorPlatform, ...] = field(
        compare=False, repr=False
    )
    deepest_floor: int
    last_landed_floor: int | None
    supported_floor: int | None
    physics_substep_accumulator: float
    health_segments: int
    last_health_delta: int
    last_conveyor_velocity_delta_x: float
    last_spring_velocity_delta_y: float
    elapsed_seconds: float
    rng_state: dict[str, object]
    flipping_runtime_states: tuple[tuple[int, str, float], ...] = ()


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
        self.supported_floor: int | None = (
            first.floor_index if config.enable_support_ownership else None
        )
        self._physics_substep_accumulator = 0.0
        self.health_segments = config.initial_health_segments
        self.last_health_delta = 0
        self.last_conveyor_velocity_delta_x = 0.0
        self.last_spring_velocity_delta_y = 0.0
        self.elapsed_seconds = 0.0
        self.last_collision_diagnostic: dict[str, object] | None = None
        self.flipping_states: dict[int, dict[str, float | str]] = {
            platform.floor_index: {"state": "READY", "elapsed": 0.0}
            for platform in self.platforms
            if platform.kind == "flipping"
        }

    def capture_snapshot(self) -> SimulatorSnapshot:
        body = self.player.body
        return SimulatorSnapshot(
            player_position=(float(body.position.x), float(body.position.y)),
            player_velocity=(float(body.velocity.x), float(body.velocity.y)),
            player_angle=float(body.angle),
            player_angular_velocity=float(body.angular_velocity),
            player_force=(float(body.force.x), float(body.force.y)),
            player_torque=float(body.torque),
            platforms=tuple(
                PlatformSnapshot(
                    floor_index=platform.floor_index,
                    center_x=platform.center_x,
                    center_y=platform.center_y,
                    kind=platform.kind,
                )
                for platform in self.platforms
            ),
            platform_objects=tuple(self.platforms),
            deepest_floor=self.deepest_floor,
            last_landed_floor=self.last_landed_floor,
            supported_floor=self.supported_floor,
            physics_substep_accumulator=self._physics_substep_accumulator,
            health_segments=self.health_segments,
            last_health_delta=self.last_health_delta,
            last_conveyor_velocity_delta_x=(
                self.last_conveyor_velocity_delta_x
            ),
            last_spring_velocity_delta_y=self.last_spring_velocity_delta_y,
            elapsed_seconds=self.elapsed_seconds,
            rng_state=deepcopy(self.rng.bit_generator.state),
            flipping_runtime_states=tuple(
                (floor_index, str(st["state"]), float(st["elapsed"]))
                for floor_index, st in self.flipping_states.items()
            ),
        )

    def restore_snapshot(self, snapshot: SimulatorSnapshot) -> None:
        if len(snapshot.platforms) != len(self.platforms):
            raise ValueError("snapshot platform count與Simulator不一致。")
        body = self.player.body
        body.position = snapshot.player_position
        body.velocity = snapshot.player_velocity
        body.angle = snapshot.player_angle
        body.angular_velocity = snapshot.player_angular_velocity
        body.force = snapshot.player_force
        body.torque = snapshot.player_torque
        for platform in self.platforms:
            if platform.body in self.space.bodies:
                self.space.remove(platform.shape, platform.body)
        if snapshot.platform_objects:
            self.platforms = list(snapshot.platform_objects)
        for platform, saved in zip(
            self.platforms, snapshot.platforms, strict=True
        ):
            platform.floor_index = saved.floor_index
            platform.body.position = (saved.center_x, saved.center_y)
            platform.kind = saved.kind
            if platform.body not in self.space.bodies:
                self.space.add(platform.body, platform.shape)
        self.deepest_floor = snapshot.deepest_floor
        self.last_landed_floor = snapshot.last_landed_floor
        self.supported_floor = snapshot.supported_floor
        self._physics_substep_accumulator = (
            snapshot.physics_substep_accumulator
        )
        self.health_segments = snapshot.health_segments
        self.last_health_delta = snapshot.last_health_delta
        self.last_conveyor_velocity_delta_x = (
            snapshot.last_conveyor_velocity_delta_x
        )
        self.last_spring_velocity_delta_y = (
            snapshot.last_spring_velocity_delta_y
        )
        self.elapsed_seconds = snapshot.elapsed_seconds
        self.rng.bit_generator.state = deepcopy(snapshot.rng_state)
        self.flipping_states = {
            floor_index: {"state": state, "elapsed": elapsed}
            for floor_index, state, elapsed in snapshot.flipping_runtime_states
        }

    def _apply_horizontal_action(
        self, action: Action, dt: float | None = None
    ) -> None:
        delta_t = self.config.dt if dt is None else dt
        velocity = self.player.body.velocity
        velocity_x = float(velocity.x)
        control_multiplier = (
            1.0
            if self.supported_platform is not None
            else self.config.air_control_multiplier
        )

        if self.config.enable_arcade_horizontal_control:
            # 1. Reversal brake
            opposite = (
                (action is Action.LEFT and velocity_x > 0.0)
                or (action is Action.RIGHT and velocity_x < 0.0)
            )
            if opposite:
                velocity_x = 0.0

            # 2. Startup impulse
            impulse = self.config.startup_impulse_speed
            if action is Action.LEFT:
                if velocity_x > -impulse:
                    velocity_x = -impulse
            elif action is Action.RIGHT:
                if velocity_x < impulse:
                    velocity_x = impulse

            # 3. Nonlinear acceleration curve
            base_accel = self.config.horizontal_acceleration
            speed_ratio = min(
                1.0,
                abs(velocity_x) / self.config.max_horizontal_speed,
            )
            remaining = max(0.0, 1.0 - speed_ratio)
            boost = self.config.startup_acceleration_multiplier
            exponent = self.config.acceleration_curve_exponent
            response_multiplier = 1.0 + (boost - 1.0) * remaining**exponent
            acceleration = base_accel * response_multiplier * control_multiplier

            # 4. Acceleration / Release
            if action is Action.LEFT:
                velocity_x -= acceleration * delta_t
            elif action is Action.RIGHT:
                velocity_x += acceleration * delta_t
            else:
                if self.config.release_deceleration is None:
                    velocity_x *= self.config.release_drag
                else:
                    decrement = self.config.release_deceleration * delta_t
                    velocity_x = float(
                        np.sign(velocity_x)
                        * max(0.0, abs(velocity_x) - decrement)
                    )
                if abs(velocity_x) < 0.5:
                    velocity_x = 0.0
        else:
            # Legacy horizontal control
            acceleration = (
                self.config.horizontal_acceleration * control_multiplier
            )
            if action is Action.LEFT:
                if velocity_x > 0:
                    acceleration *= self.config.reverse_brake_multiplier
                velocity_x -= acceleration * delta_t
            elif action is Action.RIGHT:
                if velocity_x < 0:
                    acceleration *= self.config.reverse_brake_multiplier
                velocity_x += acceleration * delta_t
            else:
                if self.config.release_deceleration is None:
                    velocity_x *= self.config.release_drag
                else:
                    decrement = self.config.release_deceleration * delta_t
                    velocity_x = float(
                        np.sign(velocity_x)
                        * max(0.0, abs(velocity_x) - decrement)
                    )
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
            if replacement.kind == "flipping":
                self.flipping_states[replacement_floor] = {
                    "state": "READY",
                    "elapsed": 0.0,
                }
            active_floors = {p.floor_index for p in self.platforms}
            self.flipping_states = {
                f: st
                for f, st in self.flipping_states.items()
                if f in active_floors
            }

    def _landing_platform(
        self,
        previous_bottom: float,
        current_bottom: float,
        previous_player_x: float,
        current_player_x: float,
        previous_tops: dict[int, float],
    ) -> SimulatorPlatform | None:
        if (
            not self.config.enable_swept_edge_collision
            and not self.config.enable_support_ownership
        ):
            if self.player.body.velocity.y > 0:
                return None
            player_left = current_player_x - self.player.width / 2
            player_right = current_player_x + self.player.width / 2
            legacy_candidates = [
                platform
                for platform in self.platforms
                if self.platform_is_active(platform)
                and player_right > platform.left
                and player_left < platform.right
                and previous_bottom >= platform.top - 1.5
                and current_bottom <= platform.top
            ]
            if not legacy_candidates:
                return None
            return max(legacy_candidates, key=lambda item: item.top)
        platform_velocity_y = (
            self.config.scroll_speed
            if self.config.enable_support_ownership
            else 0.0
        )
        if self.player.body.velocity.y > platform_velocity_y:
            if not (
                self.last_collision_diagnostic
                and self.last_collision_diagnostic.get("decision") == "landed"
            ):
                self.last_collision_diagnostic = {
                    "decision": "pass_through_rising",
                    "reason": "relative_vertical_velocity_above_platform",
                    "relative_velocity_y": float(
                        self.player.body.velocity.y - platform_velocity_y
                    ),
                    "one_way_eligible": False,
                }
            return None
        candidates: list[tuple[SimulatorPlatform, float, float]] = []
        crossed_without_overlap: dict[str, object] | None = None
        for platform in self.platforms:
            if not self.platform_is_active(platform):
                continue
            previous_top = (
                previous_tops.get(platform.floor_index, platform.top)
                if self.config.enable_support_ownership
                else platform.top
            )
            previous_gap = previous_bottom - previous_top
            current_gap = current_bottom - platform.top
            if previous_gap < -1.5 or current_gap > 0:
                continue
            relative_distance = previous_gap - current_gap
            if relative_distance <= 0:
                continue
            time_of_impact = float(
                np.clip(previous_gap / relative_distance, 0.0, 1.0)
            )
            impact_x = (
                previous_player_x
                + (current_player_x - previous_player_x) * time_of_impact
                if self.config.enable_swept_edge_collision
                else current_player_x
            )
            player_left = impact_x - self.player.width / 2
            player_right = impact_x + self.player.width / 2
            if player_right <= platform.left or player_left >= platform.right:
                crossed_without_overlap = {
                    "decision": "pass_through_no_horizontal_overlap",
                    "reason": "swept_top_crossing_outside_platform",
                    "platform_floor": platform.floor_index,
                    "time_of_impact": time_of_impact,
                    "impact_player_bbox_x": [player_left, player_right],
                    "platform_bbox_x": [platform.left, platform.right],
                    "previous_bottom": previous_bottom,
                    "current_bottom": current_bottom,
                    "previous_platform_top": previous_top,
                    "current_platform_top": platform.top,
                    "relative_velocity_y": float(
                        self.player.body.velocity.y - platform_velocity_y
                    ),
                    "one_way_eligible": True,
                }
                continue
            candidates.append((platform, time_of_impact, impact_x))
        if not candidates:
            if crossed_without_overlap is not None and not (
                self.last_collision_diagnostic
                and self.last_collision_diagnostic.get("decision") == "landed"
            ):
                self.last_collision_diagnostic = crossed_without_overlap
            return None
        platform, time_of_impact, impact_x = max(
            candidates,
            key=lambda item: item[0].top,
        )
        self.last_collision_diagnostic = {
            "decision": "landed",
            "reason": (
                "swept_top_surface_crossing"
                if self.config.enable_swept_edge_collision
                else "legacy_end_position_top_crossing"
            ),
            "platform_floor": platform.floor_index,
            "platform_kind": platform.kind,
            "time_of_impact": time_of_impact,
            "impact_x": impact_x,
            "collision_normal": [0.0, 1.0],
            "previous_bottom": previous_bottom,
            "current_bottom": current_bottom,
            "relative_velocity_y": float(
                self.player.body.velocity.y - platform_velocity_y
            ),
            "one_way_eligible": True,
        }
        return platform

    def _platform_for_floor(
        self,
        floor_index: int | None,
    ) -> SimulatorPlatform | None:
        if floor_index is None:
            return None
        return next(
            (
                platform
                for platform in self.platforms
                if platform.floor_index == floor_index
            ),
            None,
        )

    def _player_overlaps(self, platform: SimulatorPlatform) -> bool:
        player_left = self.player.body.position.x - self.player.width / 2
        player_right = self.player.body.position.x + self.player.width / 2
        return player_right > platform.left and player_left < platform.right

    @property
    def supported_platform(self) -> SimulatorPlatform | None:
        platform = self._platform_for_floor(self.supported_floor)
        if platform is None or not self.platform_is_active(platform):
            return None
        player_bottom = (
            float(self.player.body.position.y) - self.player.height / 2
        )
        if not self._player_overlaps(platform):
            return None
        if abs(player_bottom - platform.top) > 2.0:
            return None
        return platform

    def _maintain_or_release_support(
        self,
        events: list[str],
        support_departures: list[SupportDepartureRecord],
    ) -> bool:
        source = self._platform_for_floor(self.supported_floor)
        if (
            source is not None
            and self.platform_is_active(source)
            and self._player_overlaps(source)
        ):
            if source.kind == "flipping":
                self.trigger_flipping_platform(source.floor_index)
            conveyor_vx = 0.0
            if (
                self.config.enable_conveyor
                and source.kind in {"conveyor_left", "conveyor_right"}
            ):
                direction = (
                    -1.0 if source.kind == "conveyor_left" else 1.0
                )
                conveyor_vx = direction * self.config.conveyor_velocity_delta
                self.last_conveyor_velocity_delta_x = conveyor_vx
                if ("conveyor_contact", source.kind) not in events:
                    events.extend(("conveyor_contact", source.kind))
            else:
                self.last_conveyor_velocity_delta_x = 0.0

            self.player.body.position = (
                self.player.body.position.x + conveyor_vx * self.config.physics_dt,
                source.top + self.player.height / 2,
            )
            self.player.body.velocity = (
                self.player.body.velocity.x,
                self.config.scroll_speed,
            )
            return True

        event = (
            "support_departed"
            if source is not None and not self._player_overlaps(source)
            else "support_lost"
        )
        self.supported_floor = None
        self.last_conveyor_velocity_delta_x = 0.0
        self.player.body.velocity = (
            self.player.body.velocity.x,
            self.config.support_departure_velocity_y,
        )
        events.append(event)
        if event == "support_departed" and source is not None:
            player_left = (
                float(self.player.body.position.x) - self.player.width / 2
            )
            player_right = (
                float(self.player.body.position.x) + self.player.width / 2
            )
            support_departures.append(
                SupportDepartureRecord(
                    source_floor=source.floor_index,
                    clearance=max(
                        source.left - player_right,
                        player_left - source.right,
                    ),
                )
            )
        return False

    def platform_is_active(
        self,
        platform: SimulatorPlatform,
    ) -> bool:
        if (
            not self.config.enable_flipping
            or platform.kind != "flipping"
        ):
            return True
        st = self.flipping_states.get(platform.floor_index)
        if st is not None:
            if st["state"] == "INACTIVE":
                return False
            return True
        active_time = self.config.flipping_active_seconds
        inactive_time = self.config.flipping_inactive_seconds
        cycle = active_time + inactive_time
        if cycle <= 0:
            return True
        phase = self.elapsed_seconds % cycle
        return phase < active_time

    def get_flipping_status(self, platform: SimulatorPlatform) -> str:
        st = self.flipping_states.get(platform.floor_index)
        if st is None:
            return "READY"
        return str(st["state"])

    def trigger_flipping_platform(self, floor_index: int) -> None:
        if not self.config.enable_flipping:
            return
        st = self.flipping_states.get(floor_index)
        if st is not None and st["state"] == "READY":
            st["state"] = "TRIGGERED"
            st["elapsed"] = 0.0

    def _update_flipping_states(self, dt: float) -> None:
        if not self.config.enable_flipping:
            return
        for floor_index, st in list(self.flipping_states.items()):
            if st["state"] == "TRIGGERED":
                st["elapsed"] += dt
                if st["elapsed"] >= self.config.flipping_active_seconds:
                    st["state"] = "INACTIVE"
                    st["elapsed"] = 0.0
                    if self.supported_floor == floor_index:
                        self.supported_floor = None
            elif st["state"] == "INACTIVE":
                st["elapsed"] += dt
                if st["elapsed"] >= self.config.flipping_inactive_seconds:
                    st["state"] = "READY"
                    st["elapsed"] = 0.0

    def _clamp_horizontal_bounds(self) -> None:
        half_width = self.player.width / 2
        min_x = self.config.effective_playfield_left + half_width
        max_x = self.config.effective_playfield_right - half_width
        pos_x = float(self.player.body.position.x)
        vel_x = float(self.player.body.velocity.x)

        if pos_x < min_x:
            self.player.body.position = (min_x, self.player.body.position.y)
            if vel_x < 0.0:
                self.player.body.velocity = (0.0, self.player.body.velocity.y)
        elif pos_x > max_x:
            self.player.body.position = (max_x, self.player.body.position.y)
            if vel_x > 0.0:
                self.player.body.velocity = (0.0, self.player.body.velocity.y)

    def step(self, action: Action) -> SimulatorStep:
        if not self.config.enable_arcade_horizontal_control:
            self._apply_horizontal_action(action)
        self.last_collision_diagnostic = None
        events: list[str] = []
        support_departures: list[SupportDepartureRecord] = []
        terminal_reason: str | None = None
        self.last_health_delta = 0
        self.last_conveyor_velocity_delta_x = 0.0
        self.last_spring_velocity_delta_y = 0.0
        self._physics_substep_accumulator += (
            self.config.physics_hz / self.config.fps
        )
        substeps = int(self._physics_substep_accumulator)
        self._physics_substep_accumulator -= substeps
        for _ in range(substeps):
            if self.config.enable_arcade_horizontal_control:
                self._apply_horizontal_action(action, self.config.physics_dt)
            self.elapsed_seconds += self.config.physics_dt
            self._update_flipping_states(self.config.physics_dt)
            previous_tops = {
                platform.floor_index: platform.top
                for platform in self.platforms
            }
            self._move_platforms(self.config.physics_dt)
            previous_player_x = float(self.player.body.position.x)
            previous_bottom = (
                self.player.body.position.y - self.player.height / 2
            )
            self.space.step(self.config.physics_dt)
            if (
                self.config.max_fall_speed is not None
                and self.player.body.velocity.y < -self.config.max_fall_speed
            ):
                self.player.body.velocity = (
                    self.player.body.velocity.x,
                    -self.config.max_fall_speed,
                )
            self._clamp_horizontal_bounds()
            if (
                self.config.enable_support_ownership
                and self.supported_floor is not None
            ):
                self._maintain_or_release_support(
                    events, support_departures
                )
                self._recycle_platforms()
                term = self._check_top_hazard_spike_collision(events)
                if term:
                    terminal_reason = term
                continue
            current_bottom = (
                self.player.body.position.y - self.player.height / 2
            )
            platform = self._landing_platform(
                previous_bottom,
                current_bottom,
                previous_player_x,
                float(self.player.body.position.x),
                previous_tops,
            )
            if platform is not None:
                self.player.body.position = (
                    self.player.body.position.x,
                    platform.top + self.player.height / 2,
                )
                landing_velocity_y = self.config.jump_velocity
                if (
                    self.config.enable_support_ownership
                    and not (
                        self.config.enable_spring
                        and platform.kind == "spring"
                    )
                ):
                    self.supported_floor = platform.floor_index
                    landing_velocity_y = self.config.scroll_speed
                self.player.body.velocity = (
                    self.player.body.velocity.x,
                    landing_velocity_y,
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
                    self.supported_floor = None
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
                    self.trigger_flipping_platform(platform.floor_index)
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
            term = self._check_top_hazard_spike_collision(events)
            if term:
                terminal_reason = term

        if self.config.enable_health and self.health_segments <= 0:
            terminal_reason = "health_depleted"
        return SimulatorStep(
            events=tuple(events),
            terminated=terminal_reason is not None,
            terminal_reason=terminal_reason,
            health_delta=self.last_health_delta,
            conveyor_velocity_delta_x=(
                self.last_conveyor_velocity_delta_x
            ),
            spring_velocity_delta_y=self.last_spring_velocity_delta_y,
            support_departures=tuple(support_departures),
        )

    def _check_top_hazard_spike_collision(self, events: list[str]) -> str | None:
        player_screen_top = self.config.height - (
            float(self.player.body.position.y) + self.player.height / 2
        )
        if self.config.enable_calibrated_playfield:
            if player_screen_top <= self.config.effective_top_hazard_bottom:
                supports_health_top_hazard = (
                    self.config.environment_version.startswith("ns-shaft-sim-v0.7")
                    or self.config.environment_version.startswith("ns-shaft-sim-fidelity-v1")
                    or self.config.environment_version.startswith("ns-shaft-sim-fidelity-v2")
                )
                if not (
                    supports_health_top_hazard
                    and self.config.enable_health
                    and self.config.enable_spikes
                ):
                    return "top"
                # Top ceiling spike contact! Deal spike damage instead of instant death
                previous_health = self.health_segments
                self.health_segments = max(
                    0,
                    self.health_segments - self.config.spike_damage_segments,
                )
                self.last_health_delta = self.health_segments - previous_health
                if "top_spike_contact" not in events:
                    events.append("top_spike_contact")
                if self.last_health_delta < 0 and "damage" not in events:
                    events.append("damage")
                if self.health_segments <= 0:
                    if "health_depleted" not in events:
                        events.append("health_depleted")
                    return "health_depleted"
                else:
                    # Player survives top spike contact!
                    # Pass-through currently supported platform UNLESS it is spring or spikes
                    source = self._platform_for_floor(self.supported_floor)
                    if (
                        source is not None
                        and source.kind not in {"spring", "spikes"}
                    ):
                        self.supported_floor = None
                        self.player.body.position = (
                            float(self.player.body.position.x),
                            float(self.player.body.position.y) - 6.0,
                        )
                        self.player.body.velocity = (
                            float(self.player.body.velocity.x),
                            min(-100.0, float(self.player.body.velocity.y)),
                        )
                    else:
                        self.player.body.velocity = (
                            float(self.player.body.velocity.x),
                            min(-50.0, float(self.player.body.velocity.y)),
                        )
            elif player_screen_top > self.config.effective_playfield_bottom:
                return "bottom"
        elif self.player.body.position.y + self.player.height / 2 < 0:
            return "bottom"
        elif (
            self.player.body.position.y - self.player.height / 2
            > self.config.height
        ):
            return "top"
        return None
