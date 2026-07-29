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


class SafePlatformPolicy:
    """先選擇可達落點，再決定方向的可解釋規則基準。"""

    def __init__(self, config: BaselineConfig) -> None:
        self.config = config
        self.safe_kinds = set(config.safe_platform_kinds)
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
        self._coast_frames = 0

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
        action, braking = self._stabilize(desired)
        if braking:
            reason = "direction_change_brake"
        return PolicyDecision(
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

    def _landing(self, platform: dict, player_x: float, player_y: float) -> _Landing:
        box = platform.get("box") or {}
        left = float(box.get("left", 0.0))
        width = float(box.get("width", 0.0))
        right = left + width
        top = float(box.get("top", 0.0))
        margin = min(self.config.landing_margin_pixels, max(0.0, width / 3))
        safe_left = left + margin
        safe_right = right - margin
        aim_x = min(max(player_x, safe_left), safe_right)
        return _Landing(
            platform=platform,
            delta_y=top - player_y,
            horizontal_delta=aim_x - player_x,
            center_x=(left + right) / 2,
            top=top,
        )

    def _is_reachable(self, landing: _Landing) -> bool:
        horizontal_reach = (
            self.config.reachability_base_pixels
            + self.config.reachability_per_vertical_pixel
            * max(0.0, landing.delta_y)
        )
        return abs(landing.horizontal_delta) <= horizontal_reach

    def _clear_target(self) -> None:
        self._target_id = None
        self._target_kind = None
        self._target_center_x = None
        self._target_top = None

    def _detect_or_continue_launch_escape(
        self,
        observation: GameObservation,
        player_x: float,
    ) -> tuple[Action, dict, float] | None:
        clearance = self.config.launch_escape_clearance_pixels
        if any(
            str(event.get("type", "")) in {"landed", "floor_descended"}
            for event in observation.events
        ):
            self._launch_left = None
            self._launch_right = None
            self._launch_direction = None
            self._coast_frames = 0
        if (
            self._launch_left is not None
            and self._launch_right is not None
            and self._launch_direction is not None
        ):
            still_blocked = (
                self._launch_left - clearance
                <= player_x
                <= self._launch_right + clearance
            )
            if still_blocked:
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
            self._launch_left = None
            self._launch_right = None
            self._launch_direction = None

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
        direction = (
            Action.LEFT
            if player_x - left <= right - player_x
            else Action.RIGHT
        )
        self._launch_left = left
        self._launch_right = right
        self._launch_direction = direction
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
        player = observation.player
        if player is None:
            return self._decision(
                Action.RELEASE_ALL,
                "player_not_detected",
            )
        player_x = float(player.get("center_x", 0.0))
        player_y = float(player.get("center_y", 0.0))

        launch_escape = self._detect_or_continue_launch_escape(
            observation,
            player_x,
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
        for platform in observation.platforms:
            kind = str(platform.get("kind", ""))
            landing = self._landing(platform, player_x, player_y)
            if not (
                self.config.min_target_vertical_gap_pixels
                <= landing.delta_y
                <= self.config.max_target_vertical_gap_pixels
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
            top_danger = (
                player_y <= self.config.top_danger_player_y_threshold
            )
            target = self._select_locked_or_best(
                safe_candidates,
                prefer_deepest=top_danger,
            )
            if top_danger:
                reason = "move_toward_deeper_safe_platform"
        else:
            self._clear_target()
            health = int((observation.health or {}).get("segments") or 0)
            if (
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
            else:
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

        target_id = target.platform.get("track_id")
        self._target_id = int(target_id) if target_id is not None else None
        self._target_kind = str(target.platform.get("kind", ""))
        self._target_center_x = target.center_x
        self._target_top = target.top
        horizontal_delta = target.horizontal_delta
        if abs(horizontal_delta) <= self.config.horizontal_deadzone_pixels:
            return self._decision(
                Action.RELEASE_ALL,
                (
                    "aligned_with_emergency_spikes"
                    if reason == "emergency_spike_landing"
                    else (
                        "aligned_with_deeper_safe_platform"
                        if reason == "move_toward_deeper_safe_platform"
                        else "aligned_with_safe_platform"
                    )
                ),
                target=target.platform,
                horizontal_delta=horizontal_delta,
            )
        return self._decision(
            Action.RIGHT if horizontal_delta > 0 else Action.LEFT,
            reason,
            target=target.platform,
            horizontal_delta=horizontal_delta,
        )
