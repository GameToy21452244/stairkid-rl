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


class SafePlatformPolicy:
    """只朝最近的非尖刺下方平台移動；作為可解釋基準，不是 RL。"""

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

    def choose(self, observation: GameObservation) -> PolicyDecision:
        player = observation.player
        if player is None:
            return self._decision(
                Action.RELEASE_ALL,
                "player_not_detected",
            )
        player_x = float(player.get("center_x", 0.0))
        player_y = float(player.get("center_y", 0.0))

        hazards: list[tuple[float, dict, float]] = []
        for platform in observation.platforms:
            if str(platform.get("kind", "")) != "spikes":
                continue
            box = platform.get("box") or {}
            top = float(box.get("top", 0.0))
            delta_y = top - player_y
            left = float(box.get("left", 0.0))
            right = left + float(box.get("width", 0.0))
            margin = self.config.hazard_horizontal_margin_pixels
            if (
                -20.0 <= delta_y <= self.config.hazard_vertical_gap_pixels
                and left - margin <= player_x <= right + margin
            ):
                center_x = (left + right) / 2
                hazards.append((delta_y, platform, center_x - player_x))
        if hazards:
            _delta_y, hazard, horizontal_delta = min(
                hazards,
                key=lambda item: (item[0], abs(item[2])),
            )
            desired = (
                Action.LEFT
                if horizontal_delta >= 0
                else Action.RIGHT
            )
            return self._decision(
                desired,
                "avoid_nearby_spikes",
                target=hazard,
                horizontal_delta=horizontal_delta,
            )

        candidates: list[tuple[float, float, dict]] = []
        motion = str(player.get("motion", ""))
        excluded_springs: list[tuple[float, dict]] = []
        for platform in observation.platforms:
            if str(platform.get("kind", "")) not in self.safe_kinds:
                continue
            box = platform.get("box") or {}
            top = float(box.get("top", 0.0))
            delta_y = top - player_y
            if not (
                self.config.min_target_vertical_gap_pixels
                <= delta_y
                <= self.config.max_target_vertical_gap_pixels
            ):
                continue
            center_x = float(box.get("left", 0.0)) + float(
                box.get("width", 0.0)
            ) / 2
            if (
                motion == "rising"
                and delta_y
                <= self.config.rising_origin_exclusion_gap_pixels
                and abs(center_x - player_x)
                <= (
                    float(box.get("width", 0.0)) / 2
                    + self.config.rising_origin_horizontal_margin_pixels
                )
            ):
                if str(platform.get("kind", "")) == "spring":
                    excluded_springs.append((center_x, platform))
                continue
            candidates.append((delta_y, abs(center_x - player_x), platform))
        if not candidates:
            self._target_id = None
            self._target_kind = None
            self._target_center_x = None
            self._target_top = None
            if excluded_springs:
                spring_x, spring = min(
                    excluded_springs,
                    key=lambda item: abs(item[0] - player_x),
                )
                velocity_x = float(player.get("velocity_x", 0.0))
                if abs(velocity_x) >= 5.0:
                    desired = (
                        Action.RIGHT if velocity_x > 0 else Action.LEFT
                    )
                else:
                    desired = (
                        Action.LEFT
                        if player_x < spring_x
                        else Action.RIGHT
                    )
                return self._decision(
                    desired,
                    "escape_spring_bounce",
                    target=spring,
                    horizontal_delta=spring_x - player_x,
                )
            return self._decision(
                Action.RELEASE_ALL,
                "no_safe_platform",
            )

        locked = next(
            (
                item
                for item in candidates
                if item[2].get("track_id") == self._target_id
            ),
            None,
        )
        if (
            locked is None
            and self._target_kind is not None
            and self._target_center_x is not None
            and self._target_top is not None
        ):
            spatial_matches = []
            for item in candidates:
                platform = item[2]
                if str(platform.get("kind", "")) != self._target_kind:
                    continue
                box = platform.get("box") or {}
                center_x = float(box.get("left", 0.0)) + float(
                    box.get("width", 0.0)
                ) / 2
                top = float(box.get("top", 0.0))
                distance = (
                    (center_x - self._target_center_x) ** 2
                    + (top - self._target_top) ** 2
                ) ** 0.5
                if distance <= self.config.target_reacquire_distance_pixels:
                    spatial_matches.append((distance, item))
            if spatial_matches:
                locked = min(
                    spatial_matches,
                    key=lambda item: item[0],
                )[1]
        _delta_y, _distance, target = locked or min(
            candidates, key=lambda item: (item[0], item[1])
        )
        target_id = target.get("track_id")
        self._target_id = (
            int(target_id) if target_id is not None else None
        )
        box = target.get("box") or {}
        target_x = float(box.get("left", 0.0)) + float(
            box.get("width", 0.0)
        ) / 2
        self._target_kind = str(target.get("kind", ""))
        self._target_center_x = target_x
        self._target_top = float(box.get("top", 0.0))
        horizontal_delta = target_x - player_x
        if abs(horizontal_delta) <= self.config.horizontal_deadzone_pixels:
            return self._decision(
                Action.RELEASE_ALL,
                "aligned_with_safe_platform",
                target=target,
                horizontal_delta=horizontal_delta,
            )
        return self._decision(
            Action.RIGHT if horizontal_delta > 0 else Action.LEFT,
            "move_toward_safe_platform",
            target=target,
            horizontal_delta=horizontal_delta,
        )
