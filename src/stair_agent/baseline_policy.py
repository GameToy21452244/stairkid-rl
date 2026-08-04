from __future__ import annotations

from dataclasses import dataclass

from .config import BaselineConfig
from .input_controller import Action
from .observation import GameObservation


@dataclass(frozen=True)
class PolicyDecision:
    action: Action
    reason: str
    target_platform_id: int | None = None
    target_platform_kind: str | None = None
    horizontal_delta: float | None = None


@dataclass(frozen=True)
class _Landing:
    platform: dict
    delta_y: float
    horizontal_delta: float
    center_x: float
    top: float
    prediction_seconds: float
    projected_x: float
    safe_left: float
    safe_right: float


class SafePlatformPolicy:
    """先選擇可達落點，再決定方向的可解釋規則基準。"""

    def __init__(
        self,
        config: BaselineConfig,
        *,
        normal_support_departure_enabled: bool = True,
        normal_support_departure_delay_steps: int = 0,
        support_aware_launch_handoff_enabled: bool = False,
        support_contact_uses_tracker_aabb_overlap: bool = False,
    ) -> None:
        if normal_support_departure_delay_steps < 0:
            raise ValueError(
                "normal_support_departure_delay_steps 不可小於 0。"
            )
        self.config = config
        self.safe_kinds = set(config.safe_platform_kinds)
        self._normal_support_departure_enabled = bool(
            normal_support_departure_enabled
        )
        self._normal_support_departure_delay_steps = int(
            normal_support_departure_delay_steps
        )
        self._support_aware_launch_handoff_enabled = bool(
            support_aware_launch_handoff_enabled
        )
        self._support_contact_uses_tracker_aabb_overlap = bool(
            support_contact_uses_tracker_aabb_overlap
        )
        self.reset()

    def reset(self) -> None:
        self._target_id: int | None = None
        self._active_direction: Action | None = None
        self._pending_direction: Action | None = None
        self._pending_frames = 0
        self._release_frames = 0
        self._target_kind: str | None = None
        self._target_center_x: float | None = None
        self._target_top: float | None = None
        self._launch_left: float | None = None
        self._launch_right: float | None = None
        self._launch_direction: Action | None = None
        self._launch_escape_steps = 0
        self._launch_replan_cooldown = 0
        self._departure_source_id: int | None = None
        self._departure_source_kind: str | None = None
        self._departure_source_left: float | None = None
        self._departure_source_right: float | None = None
        self._departure_destination: dict | None = None
        self._departure_destination_id: int | None = None
        self._departure_destination_kind: str | None = None
        self._departure_direction: Action | None = None
        self._departure_steps = 0
        self._departure_lost_frames = 0
        self._departure_blocked_source_id: int | None = None
        self._departure_abort_cooldown_steps = 0
        self._normal_departure_candidate_source_id: int | None = None
        self._normal_departure_candidate_destination_id: int | None = None
        self._normal_departure_candidate_steps = 0
        self._coast_frames = 0
        self._special_source_id: int | None = None
        self._special_source_kind: str | None = None
        self._special_left: float | None = None
        self._special_right: float | None = None
        self._special_top: float | None = None
        self._special_direction: Action | None = None
        self._special_direction_source: str | None = None
        self._special_destination_id: int | None = None
        self._special_escape_replanned = False
        self._special_escape_steps = 0
        self._special_contact_sequence = 0
        self._special_contact_episode_id: int | None = None
        self._special_source_reacquire_count = 0
        self._special_source_reacquired = False
        self._special_replan_count = 0
        self._special_direction_reversal_count = 0
        self._special_candidate_direction: Action | None = None
        self._special_candidate_destination_id: int | None = None
        self._special_candidate_stability_steps = 0
        self._special_forced_exit_active = False
        self._special_forced_exit_steps = 0
        self._special_safety_abort_active = False
        self._special_safety_abort_count = 0
        self._special_same_source_restart_count = 0
        self._platform_bounds_by_id: dict[
            tuple[int, str], tuple[float, float, float]
        ] = {}
        self._target_lock_age_steps = 0
        self._aligned_dwell_target_id: int | None = None
        self._aligned_dwell_target_kind: str | None = None
        self._aligned_dwell_gap: float | None = None
        self._aligned_dwell_steps = 0
        self._current_player_x: float | None = None
        self._current_player_vx = 0.0
        self._current_player_vy = 0.0
        self._current_player_motion = ""
        self._last_landing_prediction_seconds: float | None = None
        self._last_landing_projected_x: float | None = None
        self._last_landing_release_projection_seconds: float | None = None
        self._last_landing_release_projected_x: float | None = None
        self._last_landing_release_horizontal_delta: float | None = None
        self._last_landing_safe_left: float | None = None
        self._last_landing_safe_right: float | None = None
        self._wall_guard_active = False
        self._wall_guard_side: str | None = None
        self._wall_guard_original_action: Action | None = None
        self._wall_cooldown_side: str | None = None
        self._wall_cooldown_steps = 0
        self._support_contact_active = False
        self._support_platform_id: int | None = None
        self._support_edge_distance: float | None = None
        self._aligned_release_streak = 0
        self._controller_phase = "reset"
        self._previous_action: Action | None = None
        self._action_streak_steps = 0
        self._recovery_active = False
        self._current_top_pressure_observed = False
        self._top_pressure_active = False
        self._top_pressure_direction: Action | None = None
        self._top_pressure_memory_steps_remaining = 0
        self._top_pressure_dropout_steps = 0
        self._top_pressure_dropout_exhausted = False
        self._top_pressure_support_settle_steps = 0

    def _stabilize(self, desired: Action) -> tuple[Action, bool]:
        if desired is Action.RELEASE_ALL:
            self._release_frames += 1
            self._pending_direction = None
            self._pending_frames = 0
            if (
                self._release_frames
                >= self.config.direction_switch_release_frames
            ):
                self._active_direction = None
            return Action.RELEASE_ALL, False

        self._release_frames = 0
        if (
            self._active_direction is None
            or self._active_direction is desired
        ):
            self._active_direction = desired
            self._pending_direction = None
            self._pending_frames = 0
            return desired, False

        if self._pending_direction is desired:
            self._pending_frames += 1
        else:
            self._pending_direction = desired
            self._pending_frames = 1
        if (
            self._pending_frames
            <= self.config.direction_switch_release_frames
        ):
            return Action.RELEASE_ALL, True

        self._active_direction = desired
        self._pending_direction = None
        self._pending_frames = 0
        return desired, False

    def _decision(
        self,
        desired: Action,
        reason: str,
        *,
        target: dict | None = None,
        horizontal_delta: float | None = None,
    ) -> PolicyDecision:
        original_desired = desired
        wall_side = self._wall_guard_side
        player_x = self._current_player_x
        if player_x is not None:
            if wall_side == "left":
                exited = (
                    player_x
                    >= self.config.playfield_left_pixels
                    + self.config.wall_evacuation_exit_margin_pixels
                    and self._current_player_vx >= -10.0
                )
            elif wall_side == "right":
                exited = (
                    player_x
                    <= self.config.playfield_right_pixels
                    - self.config.wall_evacuation_exit_margin_pixels
                    and self._current_player_vx <= 10.0
                )
            else:
                exited = False
            if exited:
                self._wall_cooldown_side = wall_side
                self._wall_cooldown_steps = (
                    self.config.wall_evacuation_cooldown_steps
                )
                wall_side = None
                self._wall_guard_side = None

            entering_side: str | None = None
            projected_wall_x = (
                player_x
                + self._current_player_vx
                * self.config.wall_guard_velocity_lookahead_seconds
            )
            if (
                wall_side is None
                and desired is Action.LEFT
                and projected_wall_x
                <= self.config.playfield_left_pixels
                + self.config.wall_guard_margin_pixels
            ):
                entering_side = "left"
            elif (
                wall_side is None
                and desired is Action.RIGHT
                and projected_wall_x
                >= self.config.playfield_right_pixels
                - self.config.wall_guard_margin_pixels
            ):
                entering_side = "right"
            if entering_side is not None:
                wall_side = entering_side
                self._wall_guard_side = entering_side
                self._clear_launch_escape()
                self._clear_aligned_dwell()

            if wall_side is not None:
                desired = (
                    Action.RIGHT if wall_side == "left" else Action.LEFT
                )
                if (
                    self._special_contact_episode_id is not None
                    and not self._special_safety_abort_active
                    and self._special_direction is not desired
                ):
                    self._special_direction = desired
                    self._special_direction_source = "wall_guard_override"
                    self._special_direction_reversal_count += 1
                    self._special_replan_count = max(
                        self._special_replan_count,
                        self.config.special_contact_replan_limit,
                    )
                    self._special_candidate_direction = None
                    self._special_candidate_destination_id = None
                    self._special_candidate_stability_steps = 0
                    self._special_escape_replanned = True
                if self._departure_direction is not None:
                    # Wall safety may change the exit side, but the departure
                    # state remains latched until the source support is gone.
                    self._departure_direction = desired
            elif self._wall_cooldown_steps > 0:
                cooldown_outward = (
                    self._wall_cooldown_side == "left"
                    and desired is Action.LEFT
                ) or (
                    self._wall_cooldown_side == "right"
                    and desired is Action.RIGHT
                )
                self._wall_cooldown_steps -= 1
                if cooldown_outward:
                    # Releasing here lets the old outward momentum or a
                    # still-latched target carry the player straight back to
                    # the wall.  Keep evacuating inward for the short,
                    # configured cooldown instead.
                    desired = (
                        Action.RIGHT
                        if self._wall_cooldown_side == "left"
                        else Action.LEFT
                    )
                    reason = "wall_guard_cooldown"
                if self._wall_cooldown_steps == 0:
                    self._wall_cooldown_side = None
        self._wall_guard_active = wall_side is not None
        self._wall_guard_side = wall_side
        self._wall_guard_original_action = (
            original_desired if wall_side is not None else None
        )
        action, braking = self._stabilize(desired)
        if braking:
            reason = "direction_change_brake"
        elif wall_side is not None:
            reason = "wall_guard_inward"
        if action is Action.RELEASE_ALL and reason.startswith("aligned"):
            self._aligned_release_streak += 1
        else:
            self._aligned_release_streak = 0
        if (
            self._current_top_pressure_observed
            and action in {Action.LEFT, Action.RIGHT}
        ):
            self._top_pressure_direction = action
        decision = PolicyDecision(
            action,
            reason,
            target_platform_id=(
                None if target is None else target.get("track_id")
            ),
            target_platform_kind=(
                None if target is None else str(target.get("kind", ""))
            ),
            horizontal_delta=horizontal_delta,
        )
        self._controller_phase = self._phase_from_reason(reason)
        if action is self._previous_action:
            self._action_streak_steps += 1
        else:
            self._previous_action = action
            self._action_streak_steps = 1
        return decision

    @staticmethod
    def _phase_from_reason(reason: str) -> str:
        if reason == "direction_change_brake":
            return "brake"
        if "launch" in reason:
            return "launch"
        if reason.startswith("support_departure") or reason == "depart_support_platform":
            return "support_departure"
        if reason.startswith("escape_special_contact") or reason == (
            "special_escape_safety_abort"
        ):
            return "special_escape"
        if reason in {"wall_guard_inward", "wall_guard_cooldown"}:
            return "wall_guard"
        if reason in {
            "top_pressure_dropout_continue",
            "escape_top_pressure_support_dwell",
        }:
            return "top_pressure_escape"
        if "recovery" in reason:
            return "recovery"
        if reason.startswith("aligned"):
            return "aligned"
        if reason.startswith(("move", "approach", "reposition")):
            return "move"
        if reason in {
            "player_not_detected",
            "no_reachable_landing",
            "top_pressure_dropout_exhausted",
        }:
            return "no_target"
        return "other"

    def memory_snapshot(self) -> dict[str, object]:
        """Return only controller state reconstructible by the live policy."""

        return {
            "controller_phase": self._controller_phase,
            "target_platform_id": self._target_id,
            "target_platform_kind": self._target_kind,
            "target_lock_age_steps": self._target_lock_age_steps,
            "aligned_dwell_steps": self._aligned_dwell_steps,
            "wall_guard_active": self._wall_guard_active,
            "wall_guard_side": self._wall_guard_side,
            "wall_guard_original_action": (
                None
                if self._wall_guard_original_action is None
                else self._wall_guard_original_action.name
            ),
            "wall_evacuation_active": self._wall_guard_active,
            "wall_evacuation_cooldown_steps": self._wall_cooldown_steps,
            "support_contact_active": self._support_contact_active,
            "support_platform_id": self._support_platform_id,
            "support_edge_distance": self._support_edge_distance,
            "aligned_release_streak": self._aligned_release_streak,
            "top_pressure_active": self._top_pressure_active,
            "top_pressure_direction": (
                None
                if self._top_pressure_direction is None
                else self._top_pressure_direction.name
            ),
            "top_pressure_memory_steps_remaining": (
                self._top_pressure_memory_steps_remaining
            ),
            "top_pressure_dropout_steps": self._top_pressure_dropout_steps,
            "top_pressure_dropout_exhausted": (
                self._top_pressure_dropout_exhausted
            ),
            "top_pressure_support_settle_steps": (
                self._top_pressure_support_settle_steps
            ),
            "active_direction": (
                None
                if self._active_direction is None
                else self._active_direction.name
            ),
            "pending_direction": (
                None
                if self._pending_direction is None
                else self._pending_direction.name
            ),
            "pending_frames": self._pending_frames,
            "release_frames": self._release_frames,
            "launch_active": self._launch_direction is not None,
            "launch_direction": (
                None
                if self._launch_direction is None
                else self._launch_direction.name
            ),
            "launch_escape_steps": self._launch_escape_steps,
            "launch_replan_cooldown_steps": self._launch_replan_cooldown,
            "support_departure_active": self._departure_direction is not None,
            "support_departure_source_id": self._departure_source_id,
            "support_departure_source_kind": self._departure_source_kind,
            "support_departure_destination_id": self._departure_destination_id,
            "support_departure_destination_kind": (
                self._departure_destination_kind
            ),
            "support_departure_direction": (
                None
                if self._departure_direction is None
                else self._departure_direction.name
            ),
            "support_departure_steps": self._departure_steps,
            "support_departure_lost_frames": self._departure_lost_frames,
            "support_departure_abort_source_id": (
                self._departure_blocked_source_id
            ),
            "support_departure_abort_cooldown_steps": (
                self._departure_abort_cooldown_steps
            ),
            "post_launch_coast_frames": self._coast_frames,
            "special_escape_active": (
                self._special_contact_episode_id is not None
            ),
            "special_contact_episode_id": self._special_contact_episode_id,
            "special_source_platform_id": self._special_source_id,
            "special_source_platform_kind": self._special_source_kind,
            "special_source_reacquired": self._special_source_reacquired,
            "special_source_reacquire_count": (
                self._special_source_reacquire_count
            ),
            "special_escape_direction": (
                None
                if self._special_direction is None
                else self._special_direction.name
            ),
            "special_escape_steps": self._special_escape_steps,
            "special_source_left": self._special_left,
            "special_source_right": self._special_right,
            "special_source_top": self._special_top,
            "special_escape_direction_source": self._special_direction_source,
            "special_escape_destination_platform_id": (
                self._special_destination_id
            ),
            "special_escape_replanned": self._special_escape_replanned,
            "special_escape_replan_count": self._special_replan_count,
            "special_escape_direction_reversal_count": (
                self._special_direction_reversal_count
            ),
            "special_escape_candidate_stability_steps": (
                self._special_candidate_stability_steps
            ),
            "special_escape_forced_exit_active": (
                self._special_forced_exit_active
            ),
            "special_escape_forced_exit_steps": (
                self._special_forced_exit_steps
            ),
            "special_escape_safety_abort_active": (
                self._special_safety_abort_active
            ),
            "special_escape_safety_abort_count": (
                self._special_safety_abort_count
            ),
            "same_special_source_restart_count": (
                self._special_same_source_restart_count
            ),
            "landing_prediction_seconds": (
                self._last_landing_prediction_seconds
            ),
            "landing_projected_x": self._last_landing_projected_x,
            "landing_release_projection_seconds": (
                self._last_landing_release_projection_seconds
            ),
            "landing_release_projected_x": (
                self._last_landing_release_projected_x
            ),
            "landing_release_horizontal_delta": (
                self._last_landing_release_horizontal_delta
            ),
            "landing_safe_left": self._last_landing_safe_left,
            "landing_safe_right": self._last_landing_safe_right,
            "recovery_active": self._recovery_active,
            "previous_action": (
                None
                if self._previous_action is None
                else self._previous_action.name
            ),
            "action_streak_steps": self._action_streak_steps,
        }

    def _landing(
        self,
        platform: dict,
        player_x: float,
        player_y: float,
    ) -> _Landing:
        box = platform.get("box") or {}
        left = float(box.get("left", 0.0))
        width = float(box.get("width", 0.0))
        right = left + width
        top = float(box.get("top", 0.0))
        margin = min(self.config.landing_margin_pixels, max(0.0, width / 3))
        safe_left = left + margin
        safe_right = right - margin
        delta_y = top - player_y
        lookahead = self._landing_prediction_seconds(delta_y)
        projected_x = player_x + self._current_player_vx * lookahead
        aim_x = min(max(projected_x, safe_left), safe_right)
        return _Landing(
            platform=platform,
            delta_y=delta_y,
            horizontal_delta=aim_x - projected_x,
            center_x=(left + right) / 2,
            top=top,
            prediction_seconds=lookahead,
            projected_x=projected_x,
            safe_left=safe_left,
            safe_right=safe_right,
        )

    def _landing_prediction_seconds(self, delta_y: float) -> float:
        if delta_y < self.config.min_target_vertical_gap_pixels:
            return 0.0
        minimum = self.config.landing_velocity_lookahead_seconds
        maximum = self.config.landing_prediction_max_seconds
        if self._current_player_motion == "rising" or self._current_player_vy < 0:
            return maximum
        downward_speed = max(
            self._current_player_vy,
            self.config.landing_vertical_speed_floor_pixels_per_second,
        )
        time_to_contact = delta_y / downward_speed
        return min(maximum, max(minimum, time_to_contact))

    def _is_reachable(self, landing: _Landing) -> bool:
        horizontal_reach = (
            self.config.reachability_base_pixels
            + self.config.reachability_per_vertical_pixel
            * max(0.0, landing.delta_y)
        )
        return abs(landing.horizontal_delta) <= horizontal_reach

    def _release_landing_horizontal_delta(
        self,
        landing: _Landing,
        player_x: float,
    ) -> float:
        # Real Gate v7 showed that RELEASE applies strong horizontal drag:
        # |vx| around 140–170 px/s produced only about 5–8 px displacement and
        # then nearly stopped.  Constant-velocity projection therefore declared
        # the player aligned 30–90 px too early.  Use the measured short release
        # coast only for the RELEASE-vs-steer decision; target reachability keeps
        # the longer controlled-motion horizon.
        seconds = min(
            landing.prediction_seconds,
            self.config.landing_release_projection_seconds,
        )
        projected_x = player_x + self._current_player_vx * seconds
        aim_x = min(max(projected_x, landing.safe_left), landing.safe_right)
        self._last_landing_release_projection_seconds = seconds
        self._last_landing_release_projected_x = projected_x
        self._last_landing_release_horizontal_delta = aim_x - projected_x
        return aim_x - projected_x

    def _clear_target(self) -> None:
        self._target_id = None
        self._target_kind = None
        self._target_center_x = None
        self._target_top = None
        self._target_lock_age_steps = 0
        self._clear_aligned_dwell()

    def _clear_launch_escape(self, *, start_cooldown: bool = False) -> None:
        self._launch_left = None
        self._launch_right = None
        self._launch_direction = None
        self._launch_escape_steps = 0
        if start_cooldown:
            self._launch_replan_cooldown = (
                self.config.launch_replan_cooldown_steps
            )

    def _clear_support_departure(
        self,
        *,
        start_launch_cooldown: bool = False,
        block_source: bool = False,
    ) -> None:
        source_id = self._departure_source_id
        self._departure_source_id = None
        self._departure_source_kind = None
        self._departure_source_left = None
        self._departure_source_right = None
        self._departure_destination = None
        self._departure_destination_id = None
        self._departure_destination_kind = None
        self._departure_direction = None
        self._departure_steps = 0
        self._departure_lost_frames = 0
        if start_launch_cooldown:
            self._launch_replan_cooldown = max(
                self._launch_replan_cooldown,
                self.config.launch_replan_cooldown_steps,
            )
        if block_source:
            self._departure_blocked_source_id = source_id
            self._departure_abort_cooldown_steps = (
                self.config.support_departure_abort_cooldown_steps
            )

    def _start_support_departure(
        self,
        source: dict,
        destination: _Landing,
        player_x: float,
    ) -> None:
        source_box = source.get("box") or {}
        left = float(source_box.get("left", 0.0))
        right = left + float(source_box.get("width", 0.0))
        source_id_raw = source.get("track_id")
        destination_id_raw = destination.platform.get("track_id")
        deadzone = self.config.horizontal_deadzone_pixels
        if player_x < destination.safe_left - deadzone:
            direction = Action.RIGHT
        elif player_x > destination.safe_right + deadzone:
            direction = Action.LEFT
        elif abs(self._current_player_vx) > 10.0:
            # While still supported, preserve the motion that is already
            # carrying the player off the source.  The longer airborne
            # intercept horizon only applies after support is lost.
            direction = (
                Action.RIGHT
                if self._current_player_vx > 0
                else Action.LEFT
            )
        else:
            center_delta = destination.center_x - player_x
            if abs(center_delta) > deadzone:
                direction = Action.RIGHT if center_delta > 0 else Action.LEFT
            else:
                direction = (
                    Action.LEFT
                    if player_x - left <= right - player_x
                    else Action.RIGHT
                )
        self._departure_source_id = (
            None if source_id_raw is None else int(source_id_raw)
        )
        self._departure_source_kind = str(source.get("kind", ""))
        self._departure_source_left = left
        self._departure_source_right = right
        self._departure_destination = destination.platform
        self._departure_destination_id = (
            None if destination_id_raw is None else int(destination_id_raw)
        )
        self._departure_destination_kind = str(
            destination.platform.get("kind", "")
        )
        self._departure_direction = direction
        self._departure_steps = 0
        self._departure_lost_frames = 0
        self._departure_blocked_source_id = None
        self._departure_abort_cooldown_steps = 0
        self._clear_launch_escape()
        self._clear_aligned_dwell()

    def _clear_normal_departure_candidate(self) -> None:
        self._normal_departure_candidate_source_id = None
        self._normal_departure_candidate_destination_id = None
        self._normal_departure_candidate_steps = 0

    def _normal_support_departure_ready(
        self,
        source: dict,
        destination: _Landing,
    ) -> bool:
        if str(source.get("kind", "")) != "normal":
            self._clear_normal_departure_candidate()
            return True
        if not self._normal_support_departure_enabled:
            self._clear_normal_departure_candidate()
            return False
        if self._normal_support_departure_delay_steps == 0:
            self._clear_normal_departure_candidate()
            return True
        source_raw = source.get("track_id")
        destination_raw = destination.platform.get("track_id")
        source_id = None if source_raw is None else int(source_raw)
        destination_id = (
            None if destination_raw is None else int(destination_raw)
        )
        if (
            source_id == self._normal_departure_candidate_source_id
            and destination_id
            == self._normal_departure_candidate_destination_id
        ):
            self._normal_departure_candidate_steps += 1
        else:
            self._normal_departure_candidate_source_id = source_id
            self._normal_departure_candidate_destination_id = destination_id
            self._normal_departure_candidate_steps = 1
        if (
            self._normal_departure_candidate_steps
            <= self._normal_support_departure_delay_steps
        ):
            return False
        self._clear_normal_departure_candidate()
        return True

    def _continue_support_departure(
        self,
        player_x: float,
    ) -> PolicyDecision | None:
        if self._departure_direction is None:
            return None
        same_source = self._support_contact_active and (
            self._departure_source_id is None
            or self._support_platform_id == self._departure_source_id
        )
        different_support = (
            self._support_contact_active
            and self._departure_source_id is not None
            and self._support_platform_id is not None
            and self._support_platform_id != self._departure_source_id
        )
        if different_support:
            self._clear_support_departure(start_launch_cooldown=True)
            return None
        if same_source:
            self._departure_lost_frames = 0
        else:
            self._departure_lost_frames += 1
            if (
                self._departure_lost_frames
                >= self.config.support_departure_lost_frames
            ):
                self._clear_support_departure(start_launch_cooldown=True)
                return None
        if self._departure_steps >= self.config.support_departure_max_steps:
            destination = self._departure_destination
            destination_id = self._departure_destination_id
            destination_kind = self._departure_destination_kind
            self._clear_support_departure(
                start_launch_cooldown=True,
                block_source=True,
            )
            return self._decision(
                Action.RELEASE_ALL,
                "support_departure_safety_abort",
                target=(
                    destination
                    if destination is not None
                    else {
                        "track_id": destination_id,
                        "kind": destination_kind,
                    }
                ),
            )
        self._departure_steps += 1
        self._target_lock_age_steps += 1
        direction = self._departure_direction
        edge = (
            self._departure_right_with_clearance()
            if direction is Action.RIGHT
            else self._departure_left_with_clearance()
        )
        return self._decision(
            direction,
            "depart_support_platform",
            target=self._departure_destination,
            horizontal_delta=edge - player_x,
        )

    def _departure_left_with_clearance(self) -> float:
        left = self._departure_source_left or 0.0
        return left - self.config.launch_escape_clearance_pixels

    def _departure_right_with_clearance(self) -> float:
        right = self._departure_source_right or 0.0
        return right + self.config.launch_escape_clearance_pixels

    def _clear_aligned_dwell(self) -> None:
        self._aligned_dwell_target_id = None
        self._aligned_dwell_target_kind = None
        self._aligned_dwell_gap = None
        self._aligned_dwell_steps = 0

    def _detect_aligned_dwell_escape(
        self,
        target: _Landing,
        player_x: float,
    ) -> tuple[Action, dict, float] | None:
        target_id_raw = target.platform.get("track_id")
        target_id = None if target_id_raw is None else int(target_id_raw)
        target_kind = str(target.platform.get("kind", ""))
        same_target = (
            target_id == self._aligned_dwell_target_id
            and target_kind == self._aligned_dwell_target_kind
        )
        stable_gap = (
            same_target
            and self._aligned_dwell_gap is not None
            and abs(target.delta_y - self._aligned_dwell_gap)
            <= self.config.aligned_platform_dwell_gap_tolerance_pixels
        )
        self._aligned_dwell_steps = (
            self._aligned_dwell_steps + 1 if stable_gap else 1
        )
        self._aligned_dwell_target_id = target_id
        self._aligned_dwell_target_kind = target_kind
        self._aligned_dwell_gap = target.delta_y
        if (
            self._aligned_dwell_steps
            < self.config.aligned_platform_dwell_escape_steps
        ):
            return None

        return self._start_aligned_escape(target, player_x)

    def _start_aligned_escape(
        self,
        target: _Landing,
        player_x: float,
    ) -> tuple[Action, dict, float]:
        box = target.platform.get("box") or {}
        left = float(box.get("left", 0.0))
        right = left + float(box.get("width", 0.0))
        direction = (
            Action.LEFT
            if player_x - left <= right - player_x
            else Action.RIGHT
        )
        self._launch_left = left
        self._launch_right = right
        self._launch_direction = direction
        self._launch_escape_steps = 1
        self._coast_frames = 0
        self._clear_aligned_dwell()
        clearance = self.config.launch_escape_clearance_pixels
        edge = right + clearance if direction is Action.RIGHT else left - clearance
        return direction, target.platform, edge - player_x

    def _clear_special_escape(self) -> None:
        self._special_contact_episode_id = None
        self._special_source_id = None
        self._special_source_kind = None
        self._special_left = None
        self._special_right = None
        self._special_top = None
        self._special_direction = None
        self._special_direction_source = None
        self._special_destination_id = None
        self._special_escape_replanned = False
        self._special_escape_steps = 0
        self._special_source_reacquire_count = 0
        self._special_source_reacquired = False
        self._special_replan_count = 0
        self._special_direction_reversal_count = 0
        self._special_candidate_direction = None
        self._special_candidate_destination_id = None
        self._special_candidate_stability_steps = 0
        self._special_forced_exit_active = False
        self._special_forced_exit_steps = 0
        self._special_safety_abort_active = False

    def _same_semantic_special_source(
        self,
        *,
        source_id: int | None,
        source_kind: str,
        left: float,
        right: float,
        player_x: float,
    ) -> bool:
        if (
            self._special_contact_episode_id is None
            or self._special_source_kind != source_kind
            or self._special_left is None
            or self._special_right is None
        ):
            return False
        if source_id is not None and source_id == self._special_source_id:
            return True
        old_width = max(1.0, self._special_right - self._special_left)
        new_width = max(1.0, right - left)
        overlap = max(
            0.0,
            min(self._special_right, right)
            - max(self._special_left, left),
        )
        old_center = (self._special_left + self._special_right) / 2.0
        new_center = (left + right) / 2.0
        horizontally_continuous = (
            overlap >= 0.5 * min(old_width, new_width)
            or abs(new_center - old_center)
            <= self.config.special_contact_reacquire_center_tolerance_pixels
        )
        clearance = self.config.launch_escape_clearance_pixels
        player_near_source = (
            min(self._special_left, left) - clearance
            <= player_x
            <= max(self._special_right, right) + clearance
        )
        return horizontally_continuous and player_near_source

    def _remember_platform_bounds(
        self,
        observation: GameObservation,
    ) -> None:
        for platform in observation.platforms:
            track_id = platform.get("track_id")
            if track_id is None:
                continue
            box = platform.get("box") or {}
            left = float(box.get("left", 0.0))
            width = float(box.get("width", 0.0))
            top = float(box.get("top", 0.0))
            normalized_id = int(track_id)
            kind = str(platform.get("kind", ""))
            cache_key = (normalized_id, kind)
            # Reinsert so pruning keeps the most recently observed tracks.
            self._platform_bounds_by_id.pop(cache_key, None)
            self._platform_bounds_by_id[cache_key] = (
                left,
                left + width,
                top,
            )
        while len(self._platform_bounds_by_id) > 64:
            oldest = next(iter(self._platform_bounds_by_id))
            self._platform_bounds_by_id.pop(oldest)

    def _special_source_bounds(
        self,
        observation: GameObservation,
        *,
        source_id: int | None,
        source_kind: str,
        player_y: float,
    ) -> tuple[float, float, float] | None:
        if source_id is not None:
            cached = self._platform_bounds_by_id.get(
                (source_id, source_kind)
            )
            if cached is not None:
                return cached
        candidates: list[tuple[float, float, float, float]] = []
        for platform in observation.platforms:
            if str(platform.get("kind", "")) != source_kind:
                continue
            box = platform.get("box") or {}
            left = float(box.get("left", 0.0))
            width = float(box.get("width", 0.0))
            top = float(box.get("top", 0.0))
            candidates.append(
                (abs(top - player_y), left, left + width, top)
            )
        if not candidates:
            return None
        _distance, left, right, top = min(
            candidates,
            key=lambda item: item[0],
        )
        return left, right, top

    def _preferred_special_escape_direction(
        self,
        observation: GameObservation,
        *,
        source_id: int | None,
        source_kind: str,
        source_left: float,
        source_right: float,
        source_top: float,
        player_x: float,
        player_y: float,
        allow_fallback: bool,
    ) -> tuple[Action, int | None, str] | None:
        future: list[_Landing] = []
        for candidate in observation.platforms:
            candidate_id_raw = candidate.get("track_id")
            candidate_id = (
                None
                if candidate_id_raw is None
                else int(candidate_id_raw)
            )
            kind = str(candidate.get("kind", ""))
            box = candidate.get("box") or {}
            left = float(box.get("left", 0.0))
            right = left + float(box.get("width", 0.0))
            top = float(box.get("top", 0.0))
            same_source = (
                source_id is not None and candidate_id == source_id
            ) or (
                source_id is None
                and kind == source_kind
                and abs(top - source_top)
                <= self.config.aligned_platform_dwell_gap_tolerance_pixels
                and abs(left - source_left) <= 2.0
                and abs(right - source_right) <= 2.0
            )
            if same_source or kind not in self.safe_kinds:
                continue
            if (
                top
                < source_top + self.config.min_target_vertical_gap_pixels
            ):
                continue
            landing = self._landing(candidate, player_x, player_y)
            if not (
                self.config.min_target_vertical_gap_pixels
                <= landing.delta_y
                <= self.config.max_target_vertical_gap_pixels
                and self._is_reachable(landing)
            ):
                continue
            future.append(landing)

        if future:
            destination = min(
                future,
                key=lambda item: (
                    item.delta_y,
                    abs(item.horizontal_delta),
                ),
            )
            delta = destination.horizontal_delta
            if abs(delta) > self.config.horizontal_deadzone_pixels:
                destination_id_raw = destination.platform.get("track_id")
                return (
                    Action.RIGHT if delta > 0 else Action.LEFT,
                    (
                        None
                        if destination_id_raw is None
                        else int(destination_id_raw)
                    ),
                    "visible_landing",
                )

        if not allow_fallback:
            return None
        guard = self.config.special_escape_edge_guard_pixels
        velocity_threshold = getattr(
            self.config,
            "special_escape_outward_velocity_threshold_pixels_per_second",
        )
        # Once the player already has outward momentum at a source edge,
        # reversing direction keeps it on spring/spikes and makes the next
        # frame reverse again.  Commit through the edge; the global wall
        # guard and airborne landing intercept remain responsible for safety.
        if (
            player_x >= source_right - guard
            and self._current_player_vx > velocity_threshold
        ):
            return Action.RIGHT, None, "edge_momentum_commit"
        if (
            player_x <= source_left + guard
            and self._current_player_vx < -velocity_threshold
        ):
            return Action.LEFT, None, "edge_momentum_commit"
        clearance = self.config.launch_escape_clearance_pixels
        left_exit_distance = abs(
            source_left - clearance - player_x
        )
        right_exit_distance = abs(
            source_right + clearance - player_x
        )
        if (
            abs(left_exit_distance - right_exit_distance)
            > self.config.horizontal_deadzone_pixels
        ):
            return (
                (
                    Action.LEFT
                    if left_exit_distance < right_exit_distance
                    else Action.RIGHT
                ),
                None,
                "nearest_edge",
            )
        if self._launch_direction in {Action.LEFT, Action.RIGHT}:
            return self._launch_direction, None, "launch_memory"
        if self._active_direction in {Action.LEFT, Action.RIGHT}:
            return self._active_direction, None, "active_direction"
        direction = (
            Action.LEFT
            if left_exit_distance <= right_exit_distance
            else Action.RIGHT
        )
        return direction, None, "nearest_edge"

    def _start_special_escape(
        self,
        observation: GameObservation,
        *,
        source_id: int | None,
        source_kind: str,
        player_x: float,
        player_y: float,
    ) -> bool:
        bounds = self._special_source_bounds(
            observation,
            source_id=source_id,
            source_kind=source_kind,
            player_y=player_y,
        )
        if bounds is None:
            return False
        left, right, top = bounds
        same_source = self._same_semantic_special_source(
            source_id=source_id,
            source_kind=source_kind,
            left=left,
            right=right,
            player_x=player_x,
        )
        if same_source:
            if (
                source_id is not None
                and source_id != self._special_source_id
            ):
                self._special_source_reacquire_count += 1
                self._special_source_reacquired = True
            self._special_source_id = source_id
            self._special_source_kind = source_kind
            self._special_left = left
            self._special_right = right
            self._special_top = top
            self._clear_launch_escape()
            self._clear_support_departure()
            self._coast_frames = 0
            return True

        preferred = self._preferred_special_escape_direction(
            observation,
            source_id=source_id,
            source_kind=source_kind,
            source_left=left,
            source_right=right,
            source_top=top,
            player_x=player_x,
            player_y=player_y,
            allow_fallback=True,
        )
        if preferred is None:
            return False
        direction, destination_id, direction_source = preferred
        if self._special_contact_episode_id is not None:
            self._clear_special_escape()
        self._special_contact_sequence += 1
        self._special_contact_episode_id = self._special_contact_sequence
        self._special_source_id = source_id
        self._special_source_kind = source_kind
        self._special_left = left
        self._special_right = right
        self._special_top = top
        self._special_direction = direction
        self._special_direction_source = direction_source
        self._special_destination_id = destination_id
        self._special_escape_steps = 0
        self._special_source_reacquire_count = 0
        self._special_replan_count = 0
        self._special_direction_reversal_count = 0
        self._special_candidate_direction = None
        self._special_candidate_destination_id = None
        self._special_candidate_stability_steps = 0
        self._special_forced_exit_active = False
        self._special_forced_exit_steps = 0
        self._special_safety_abort_active = False
        # Special-contact state supersedes the generic launch heuristic.
        self._clear_launch_escape()
        self._clear_support_departure()
        self._coast_frames = 0
        return True

    def _update_special_escape_replan(
        self,
        observation: GameObservation,
        *,
        player_x: float,
        player_y: float,
    ) -> None:
        if (
            self._special_contact_episode_id is None
            or self._special_direction is None
            or self._special_left is None
            or self._special_right is None
            or self._special_top is None
            or self._special_source_kind is None
            or self._special_forced_exit_active
            or self._special_safety_abort_active
            or self._special_replan_count
            >= self.config.special_contact_replan_limit
        ):
            self._special_candidate_direction = None
            self._special_candidate_destination_id = None
            self._special_candidate_stability_steps = 0
            return
        preferred = self._preferred_special_escape_direction(
            observation,
            source_id=self._special_source_id,
            source_kind=self._special_source_kind,
            source_left=self._special_left,
            source_right=self._special_right,
            source_top=self._special_top,
            player_x=player_x,
            player_y=player_y,
            allow_fallback=False,
        )
        if preferred is None:
            self._special_candidate_direction = None
            self._special_candidate_destination_id = None
            self._special_candidate_stability_steps = 0
            return
        direction, destination_id, direction_source = preferred
        if direction is self._special_direction:
            self._special_destination_id = destination_id
            self._special_candidate_direction = None
            self._special_candidate_destination_id = None
            self._special_candidate_stability_steps = 0
            return
        if direction is self._special_candidate_direction:
            self._special_candidate_stability_steps += 1
            self._special_candidate_destination_id = destination_id
        else:
            self._special_candidate_direction = direction
            self._special_candidate_destination_id = destination_id
            self._special_candidate_stability_steps = 1
        if (
            self._special_escape_steps
            < self.config.special_contact_direction_commit_steps
            or self._special_candidate_stability_steps
            < self.config.special_contact_destination_stability_steps
        ):
            return
        self._special_direction = direction
        self._special_destination_id = destination_id
        self._special_direction_source = direction_source
        self._special_replan_count += 1
        self._special_direction_reversal_count += 1
        self._special_escape_replanned = True
        self._special_candidate_direction = None
        self._special_candidate_destination_id = None
        self._special_candidate_stability_steps = 0

    def _detect_or_continue_special_escape(
        self,
        observation: GameObservation,
        player_x: float,
        player_y: float,
    ) -> tuple[Action, dict, float, str] | None:
        special_kinds = {"spring", "spikes"}
        special_source: tuple[int | None, str] | None = None
        safe_landing = False
        for event in observation.events:
            event_type = str(event.get("type", ""))
            source_kind = str(event.get("source_platform_kind") or "")
            source_id_raw = event.get("source_platform_id")
            source_id = (
                None if source_id_raw is None else int(source_id_raw)
            )
            if (
                source_kind in special_kinds
                and event_type
                in {"landed", "floor_descended", "spring_bounce", "spike_damage"}
            ):
                special_source = (source_id, source_kind)
            elif (
                event_type in {"landed", "floor_descended"}
                and source_kind
                and source_kind not in special_kinds
            ):
                safe_landing = True

        # Event-to-platform correlation can be lost after scrolling or when
        # damage/bounce arrives several frames after contact.  The nearest-
        # platform payload is deployable visual evidence, so use close
        # spring/spike geometry as a conservative fallback instead of waiting
        # for an event that may have been associated with the previous floor.
        nearest = observation.nearest_platform or {}
        nearest_kind = str(nearest.get("kind", ""))
        nearest_gap_raw = nearest.get("vertical_gap")
        nearest_gap = (
            None
            if nearest_gap_raw is None
            else float(nearest_gap_raw)
        )
        if (
            special_source is None
            and nearest_kind in special_kinds
            and nearest_gap is not None
            and 0.0 <= nearest_gap <= self.config.launch_platform_vertical_gap_pixels
        ):
            nearest_id_raw = nearest.get("track_id")
            special_source = (
                None if nearest_id_raw is None else int(nearest_id_raw),
                nearest_kind,
            )

        if special_source is not None:
            self._start_special_escape(
                observation,
                source_id=special_source[0],
                source_kind=special_source[1],
                player_x=player_x,
                player_y=player_y,
            )
        elif safe_landing:
            self._clear_special_escape()
            return None
        if self._special_contact_episode_id is None:
            return None
        self._update_special_escape_replan(
            observation,
            player_x=player_x,
            player_y=player_y,
        )
        if (
            self._special_left is None
            or self._special_right is None
            or self._special_direction is None
        ):
            return None
        clearance = self.config.launch_escape_clearance_pixels
        if not (
            self._special_left - clearance
            <= player_x
            <= self._special_right + clearance
        ):
            self._coast_frames = self.config.post_launch_coast_frames
            self._clear_special_escape()
            return None

        source = {
            "track_id": self._special_source_id,
            "kind": self._special_source_kind,
        }
        if self._special_safety_abort_active:
            return (
                Action.RELEASE_ALL,
                source,
                0.0,
                "special_escape_safety_abort",
            )
        if (
            self._special_escape_steps
            >= self.config.special_contact_escape_max_steps
        ):
            self._special_forced_exit_active = True
            self._special_candidate_direction = None
            self._special_candidate_destination_id = None
            self._special_candidate_stability_steps = 0
        if (
            self._special_forced_exit_active
            and self._special_forced_exit_steps
            >= self.config.special_contact_forced_exit_steps
        ):
            self._special_safety_abort_active = True
            self._special_safety_abort_count += 1
            return (
                Action.RELEASE_ALL,
                source,
                0.0,
                "special_escape_safety_abort",
            )

        self._special_escape_steps += 1
        if self._special_forced_exit_active:
            self._special_forced_exit_steps += 1
        edge = (
            self._special_right + clearance
            if self._special_direction is Action.RIGHT
            else self._special_left - clearance
        )
        reason = (
            "escape_special_contact_forced_exit"
            if self._special_forced_exit_active
            else "escape_special_contact"
        )
        return self._special_direction, source, edge - player_x, reason

    def _set_target(self, target: _Landing) -> None:
        target_id = target.platform.get("track_id")
        normalized_id = int(target_id) if target_id is not None else None
        if normalized_id is not None and normalized_id == self._target_id:
            self._target_lock_age_steps += 1
        else:
            self._target_lock_age_steps = 1 if normalized_id is not None else 0
        self._target_id = normalized_id
        self._target_kind = str(target.platform.get("kind", ""))
        self._target_center_x = target.center_x
        self._target_top = target.top
        self._last_landing_prediction_seconds = target.prediction_seconds
        self._last_landing_projected_x = target.projected_x
        self._last_landing_safe_left = target.safe_left
        self._last_landing_safe_right = target.safe_right

    def _detect_or_continue_launch_escape(
        self,
        observation: GameObservation,
        player_x: float,
        *,
        require_reachable_future_target: bool = False,
    ) -> tuple[Action, dict, float] | None:
        clearance = self.config.launch_escape_clearance_pixels
        if any(
            str(event.get("type", "")) in {"landed", "floor_descended"}
            for event in observation.events
        ):
            self._clear_launch_escape()
            self._coast_frames = 0
        if (
            self._launch_left is not None
            and self._launch_right is not None
            and self._launch_direction is not None
        ):
            if (
                self._launch_escape_steps
                >= self.config.launch_commit_max_steps
            ):
                self._coast_frames = self.config.post_launch_coast_frames
                self._clear_launch_escape(start_cooldown=True)
                return None
            still_blocked = (
                self._launch_left - clearance
                <= player_x
                <= self._launch_right + clearance
            )
            if still_blocked:
                self._launch_escape_steps += 1
                placeholder = {
                    "track_id": None,
                    "kind": "launch_platform",
                }
                edge = (
                    self._launch_right + clearance
                    if self._launch_direction is Action.RIGHT
                    else self._launch_left - clearance
                )
                return self._launch_direction, placeholder, edge - player_x
            self._coast_frames = self.config.post_launch_coast_frames
            self._clear_launch_escape(start_cooldown=True)

        if self._launch_replan_cooldown > 0:
            self._launch_replan_cooldown -= 1
            return None

        player = observation.player or {}
        motion = str(player.get("motion", ""))
        if motion not in {"rising", "falling"}:
            return None

        player_y = float(player.get("center_y", 0.0))
        launch_matches: list[tuple[float, dict, float, float]] = []
        for platform in observation.platforms:
            kind = str(platform.get("kind", ""))
            if kind not in self.safe_kinds and kind != "spikes":
                continue
            if motion == "falling" and kind != "spikes":
                continue
            box = platform.get("box") or {}
            left = float(box.get("left", 0.0))
            right = left + float(box.get("width", 0.0))
            delta_y = float(box.get("top", 0.0)) - player_y
            if (
                0.0 <= delta_y
                <= self.config.launch_platform_vertical_gap_pixels
                and left - clearance <= player_x <= right + clearance
            ):
                launch_matches.append((delta_y, platform, left, right))
        if not launch_matches:
            return None

        _gap, platform, left, right = min(
            launch_matches,
            key=lambda item: item[0],
        )
        future_safe: list[_Landing] = []
        future_spikes: list[_Landing] = []
        launch_id = platform.get("track_id")
        for candidate in observation.platforms:
            if candidate.get("track_id") == launch_id:
                continue
            landing = self._landing(candidate, player_x, player_y)
            if not (
                landing.delta_y > _gap
                and landing.delta_y
                <= self.config.max_target_vertical_gap_pixels
            ):
                continue
            if (
                require_reachable_future_target
                and not self._is_reachable(landing)
            ):
                continue
            kind = str(candidate.get("kind", ""))
            if kind == "spikes":
                future_spikes.append(landing)
            elif kind in self.safe_kinds:
                future_safe.append(landing)

        health = int((observation.health or {}).get("segments") or 0)
        recovering = 0 < health < self.config.recovery_full_health_segments
        recovery_targets = [
            item
            for item in future_safe
            if str(item.platform.get("kind", "")) == "normal"
        ]
        future_target: _Landing | None = None
        if recovering and recovery_targets:
            future_target = min(
                recovery_targets,
                key=lambda item: (
                    item.delta_y,
                    abs(item.horizontal_delta),
                ),
            )
        elif future_safe:
            future_target = min(
                future_safe,
                key=lambda item: (
                    item.delta_y,
                    abs(item.horizontal_delta),
                ),
            )
        elif (
            health >= self.config.emergency_spike_min_health_segments
            and future_spikes
        ):
            future_target = min(
                future_spikes,
                key=lambda item: (
                    item.delta_y,
                    abs(item.horizontal_delta),
                ),
            )

        if require_reachable_future_target and future_target is None:
            return None

        future_delta = (
            None
            if future_target is None
            else (
                future_target.horizontal_delta
                if abs(future_target.horizontal_delta)
                > self.config.horizontal_deadzone_pixels
                else future_target.center_x - player_x
            )
        )
        if (
            future_delta is not None
            and abs(future_delta) > self.config.horizontal_deadzone_pixels
        ):
            direction = Action.RIGHT if future_delta > 0 else Action.LEFT
        else:
            direction = (
                Action.LEFT
                if player_x - left <= right - player_x
                else Action.RIGHT
            )
        self._launch_left = left
        self._launch_right = right
        self._launch_direction = direction
        self._launch_escape_steps = 1
        self._coast_frames = 0
        edge = right + clearance if direction is Action.RIGHT else left - clearance
        return direction, platform, edge - player_x

    def _select_locked_or_best(
        self,
        candidates: list[_Landing],
        *,
        prefer_deepest: bool = False,
    ) -> _Landing:
        if prefer_deepest:
            return max(
                candidates,
                key=lambda item: (
                    item.delta_y
                    - self.config.deep_landing_horizontal_cost
                    * abs(item.horizontal_delta),
                    -abs(item.horizontal_delta),
                ),
            )
        locked = next(
            (
                item
                for item in candidates
                if item.platform.get("track_id") == self._target_id
            ),
            None,
        )
        if (
            locked is None
            and self._target_kind is not None
            and self._target_center_x is not None
            and self._target_top is not None
        ):
            spatial = [
                item
                for item in candidates
                if str(item.platform.get("kind", "")) == self._target_kind
                and (
                    (item.center_x - self._target_center_x) ** 2
                    + (item.top - self._target_top) ** 2
                )
                ** 0.5
                <= self.config.target_reacquire_distance_pixels
            ]
            if spatial:
                locked = min(
                    spatial,
                    key=lambda item: (
                        (item.center_x - self._target_center_x) ** 2
                        + (item.top - self._target_top) ** 2
                    ),
                )
        return locked or min(
            candidates,
            key=lambda item: (
                item.delta_y,
                abs(item.horizontal_delta),
            ),
        )

    def choose(self, observation: GameObservation) -> PolicyDecision:
        self._current_player_x = None
        self._current_player_vx = 0.0
        self._current_player_vy = 0.0
        self._current_player_motion = ""
        self._last_landing_prediction_seconds = None
        self._last_landing_projected_x = None
        self._last_landing_release_projection_seconds = None
        self._last_landing_release_projected_x = None
        self._last_landing_release_horizontal_delta = None
        self._last_landing_safe_left = None
        self._last_landing_safe_right = None
        self._special_escape_replanned = False
        self._special_source_reacquired = False
        self._current_top_pressure_observed = False
        self._support_contact_active = False
        self._support_platform_id = None
        self._support_edge_distance = None
        health = int((observation.health or {}).get("segments") or 0)
        self._recovery_active = (
            0 < health < self.config.recovery_full_health_segments
        )
        player = observation.player
        if player is None:
            self._clear_normal_departure_candidate()
            if (
                self._top_pressure_direction is not None
                and self._top_pressure_memory_steps_remaining > 0
            ):
                self._top_pressure_active = True
                if (
                    self._top_pressure_dropout_steps
                    < self.config.top_pressure_dropout_continue_steps
                ):
                    self._top_pressure_dropout_steps += 1
                    self._top_pressure_memory_steps_remaining -= 1
                    return self._decision(
                        self._top_pressure_direction,
                        "top_pressure_dropout_continue",
                    )
                self._top_pressure_dropout_exhausted = True
                return self._decision(
                    Action.RELEASE_ALL,
                    "top_pressure_dropout_exhausted",
                )
            self._top_pressure_active = False
            return self._decision(
                Action.RELEASE_ALL,
                "player_not_detected",
            )
        player_x = float(player.get("center_x", 0.0))
        player_y = float(player.get("center_y", 0.0))
        self._current_player_x = player_x
        self._current_player_vx = float(player.get("velocity_x", 0.0))
        self._current_player_vy = float(player.get("velocity_y", 0.0))
        self._current_player_motion = str(player.get("motion", ""))
        top_danger = (
            player_y <= self.config.top_danger_player_y_threshold
        )
        self._current_top_pressure_observed = top_danger
        self._top_pressure_dropout_steps = 0
        self._top_pressure_dropout_exhausted = False
        if top_danger:
            self._top_pressure_active = True
            self._top_pressure_memory_steps_remaining = (
                self.config.top_pressure_memory_steps
            )
        else:
            self._top_pressure_memory_steps_remaining = max(
                0,
                self._top_pressure_memory_steps_remaining - 1,
            )
            self._top_pressure_active = (
                self._top_pressure_memory_steps_remaining > 0
            )
            self._top_pressure_support_settle_steps = 0
            if not self._top_pressure_active:
                self._top_pressure_direction = None
        self._remember_platform_bounds(observation)
        nearest = observation.nearest_platform or {}
        nearest_gap_raw = nearest.get("vertical_gap")
        nearest_gap = (
            None
            if nearest_gap_raw is None
            else float(nearest_gap_raw)
        )
        nearest_box = nearest.get("box") or {}
        if nearest_gap is not None and 0.0 <= nearest_gap <= 12.0:
            left = float(nearest_box.get("left", 0.0))
            right = left + float(nearest_box.get("width", 0.0))
            tracker_overlap_is_support = (
                self._support_contact_uses_tracker_aabb_overlap
                or left <= player_x <= right
            )
            if right > left and tracker_overlap_is_support:
                self._support_contact_active = True
                support_id = nearest.get("track_id")
                self._support_platform_id = (
                    None if support_id is None else int(support_id)
                )
                self._support_edge_distance = min(
                    player_x - left,
                    right - player_x,
                )
        if (
            not self._support_contact_active
            or self._support_platform_id
            != self._departure_blocked_source_id
        ):
            self._departure_blocked_source_id = None
            self._departure_abort_cooldown_steps = 0

        special_escape = self._detect_or_continue_special_escape(
            observation,
            player_x,
            player_y,
        )
        if special_escape is not None:
            direction, platform, horizontal_delta, reason = special_escape
            self._clear_target()
            return self._decision(
                direction,
                reason,
                target=platform,
                horizontal_delta=horizontal_delta,
            )

        departure = self._continue_support_departure(player_x)
        if departure is not None:
            return departure

        launch_escape = None
        support_launch_overlap = (
            self._support_aware_launch_handoff_enabled
            and self._support_contact_active
            and self._current_player_motion in {"rising", "falling"}
        )
        if not self._support_contact_active or support_launch_overlap:
            launch_escape = self._detect_or_continue_launch_escape(
                observation,
                player_x,
                require_reachable_future_target=support_launch_overlap,
            )
        if launch_escape is not None:
            direction, platform, horizontal_delta = launch_escape
            self._clear_target()
            return self._decision(
                direction,
                "escape_launch_platform",
                target=platform,
                horizontal_delta=horizontal_delta,
            )

        safe_candidates: list[_Landing] = []
        spike_candidates: list[_Landing] = []
        visible_safe_candidates: list[_Landing] = []
        visible_spike_candidates: list[_Landing] = []
        for platform in observation.platforms:
            kind = str(platform.get("kind", ""))
            landing = self._landing(platform, player_x, player_y)
            if not (
                0.0
                <= landing.delta_y
                <= self.config.max_target_vertical_gap_pixels
            ):
                continue
            if kind == "spikes":
                visible_spike_candidates.append(landing)
            elif kind in self.safe_kinds:
                visible_safe_candidates.append(landing)
            else:
                continue
            if not (
                self.config.min_target_vertical_gap_pixels
                <= landing.delta_y
            ):
                continue
            if not self._is_reachable(landing):
                continue
            if kind == "spikes":
                spike_candidates.append(landing)
                continue
            if kind not in self.safe_kinds:
                continue
            safe_candidates.append(landing)

        reason = "move_toward_safe_platform"
        if safe_candidates:
            health = int((observation.health or {}).get("segments") or 0)
            recovering = (
                0 < health < self.config.recovery_full_health_segments
            )
            recovery_candidates = [
                item
                for item in safe_candidates
                if str(item.platform.get("kind", "")) == "normal"
            ]
            if top_danger:
                # Immediate top-death avoidance has priority over healing;
                # the old ordering could remain aligned with a nearby normal
                # platform while the whole sequence carried the player up.
                target = self._select_locked_or_best(
                    safe_candidates,
                    prefer_deepest=True,
                )
                reason = "move_toward_deeper_safe_platform"
            elif recovering and recovery_candidates:
                # Normal platforms are the only healing platforms. Ignore a
                # previously locked deeper target while damaged so the teacher
                # does not skip an observable recovery opportunity.
                target = min(
                    recovery_candidates,
                    key=lambda item: (
                        item.delta_y,
                        abs(item.horizontal_delta),
                    ),
                )
                reason = "move_toward_recovery_platform"
            else:
                target = self._select_locked_or_best(
                    safe_candidates,
                    prefer_deepest=top_danger,
                )
                if top_danger:
                    reason = "move_toward_deeper_safe_platform"
        else:
            health = int((observation.health or {}).get("segments") or 0)
            recovering = (
                0 < health < self.config.recovery_full_health_segments
            )
            visible_recovery_candidates = [
                item
                for item in visible_safe_candidates
                if str(item.platform.get("kind", "")) == "normal"
            ]
            if recovering and visible_recovery_candidates:
                target = min(
                    visible_recovery_candidates,
                    key=lambda item: (
                        item.delta_y,
                        abs(item.horizontal_delta),
                    ),
                )
                reason = "approach_visible_recovery_platform"
            elif visible_safe_candidates:
                target = self._select_locked_or_best(
                    visible_safe_candidates,
                )
                reason = "approach_visible_safe_platform"
            elif (
                player_y <= self.config.top_danger_player_y_threshold
                and health
                >= self.config.emergency_spike_min_health_segments
                and spike_candidates
            ):
                target = min(
                    spike_candidates,
                    key=lambda item: (
                        item.delta_y,
                        abs(item.horizontal_delta),
                    ),
                )
                reason = "emergency_spike_landing"
            elif (
                health
                >= self.config.emergency_spike_min_health_segments
                and visible_spike_candidates
            ):
                target = min(
                    visible_spike_candidates,
                    key=lambda item: (
                        item.delta_y,
                        abs(item.horizontal_delta),
                    ),
                )
                reason = "approach_visible_emergency_spikes"
            else:
                self._clear_target()
                if (
                    self._coast_frames > 0
                ):
                    self._coast_frames -= 1
                    center_delta = (
                        self.config.fallback_center_x_pixels - player_x
                    )
                    desired = (
                        Action.RELEASE_ALL
                        if abs(center_delta)
                        <= self.config.horizontal_deadzone_pixels
                        else (
                            Action.RIGHT
                            if center_delta > 0
                            else Action.LEFT
                        )
                    )
                    return self._decision(
                        desired,
                        "reposition_for_unseen_landing",
                        horizontal_delta=center_delta,
                    )
                return self._decision(
                    Action.RELEASE_ALL,
                    "no_reachable_landing",
                )

        self._set_target(target)
        target_id_raw = target.platform.get("track_id")
        target_id = None if target_id_raw is None else int(target_id_raw)
        if (
            self._support_contact_active
            and target_id != self._support_platform_id
        ):
            if self._departure_blocked_source_id == self._support_platform_id:
                if self._departure_abort_cooldown_steps > 0:
                    self._clear_normal_departure_candidate()
                    self._departure_abort_cooldown_steps -= 1
                    return self._decision(
                        Action.RELEASE_ALL,
                        "support_departure_abort_cooldown",
                        target=target.platform,
                        horizontal_delta=target.horizontal_delta,
                    )
                self._departure_blocked_source_id = None
            if self._normal_support_departure_ready(nearest, target):
                self._start_support_departure(nearest, target, player_x)
                departure = self._continue_support_departure(player_x)
                if departure is not None:
                    return departure
        else:
            self._clear_normal_departure_candidate()
        horizontal_delta = self._release_landing_horizontal_delta(
            target,
            player_x,
        )
        if abs(horizontal_delta) <= self.config.horizontal_deadzone_pixels:
            same_support_under_pressure = (
                top_danger
                and self._support_contact_active
                and target_id == self._support_platform_id
            )
            if same_support_under_pressure:
                self._top_pressure_support_settle_steps += 1
                if (
                    self._top_pressure_support_settle_steps
                    >= self.config.top_pressure_support_settle_steps
                ):
                    direction, platform, escape_delta = (
                        self._start_aligned_escape(target, player_x)
                    )
                    self._top_pressure_support_settle_steps = 0
                    self._clear_target()
                    return self._decision(
                        direction,
                        "escape_top_pressure_support_dwell",
                        target=platform,
                        horizontal_delta=escape_delta,
                    )
            else:
                self._top_pressure_support_settle_steps = 0
            dwell_escape = self._detect_aligned_dwell_escape(
                target,
                player_x,
            )
            if dwell_escape is not None:
                direction, platform, escape_delta = dwell_escape
                self._clear_target()
                return self._decision(
                    direction,
                    "escape_launch_platform_dwell",
                    target=platform,
                    horizontal_delta=escape_delta,
                )
            aligned_reason = "aligned_with_safe_platform"
            if reason == "emergency_spike_landing":
                aligned_reason = "aligned_with_emergency_spikes"
            elif reason == "move_toward_recovery_platform":
                aligned_reason = "aligned_with_recovery_platform"
            elif reason == "move_toward_deeper_safe_platform":
                aligned_reason = "aligned_with_deeper_safe_platform"
            elif reason == "approach_visible_recovery_platform":
                aligned_reason = "aligned_with_visible_recovery_platform"
            elif reason == "approach_visible_safe_platform":
                aligned_reason = "aligned_with_visible_safe_platform"
            elif reason == "approach_visible_emergency_spikes":
                aligned_reason = "aligned_with_visible_emergency_spikes"
            return self._decision(
                Action.RELEASE_ALL,
                aligned_reason,
                target=target.platform,
                horizontal_delta=horizontal_delta,
            )
        self._clear_aligned_dwell()
        self._top_pressure_support_settle_steps = 0
        return self._decision(
            Action.RIGHT if horizontal_delta > 0 else Action.LEFT,
            reason,
            target=target.platform,
            horizontal_delta=horizontal_delta,
        )
