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

    def choose(self, observation: GameObservation) -> PolicyDecision:
        player = observation.player
        if player is None:
            return PolicyDecision(Action.RELEASE_ALL, "player_not_detected")
        player_x = float(player.get("center_x", 0.0))
        player_y = float(player.get("center_y", 0.0))
        candidates: list[tuple[float, float, dict]] = []
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
            candidates.append((delta_y, abs(center_x - player_x), platform))
        if not candidates:
            return PolicyDecision(Action.RELEASE_ALL, "no_safe_platform")

        _delta_y, _distance, target = min(
            candidates,
            key=lambda item: (item[0], item[1]),
        )
        box = target.get("box") or {}
        target_x = float(box.get("left", 0.0)) + float(
            box.get("width", 0.0)
        ) / 2
        horizontal_delta = target_x - player_x
        common = {
            "target_platform_id": target.get("track_id"),
            "target_platform_kind": str(target.get("kind", "")),
            "horizontal_delta": horizontal_delta,
        }
        if abs(horizontal_delta) <= self.config.horizontal_deadzone_pixels:
            return PolicyDecision(
                Action.RELEASE_ALL,
                "aligned_with_safe_platform",
                **common,
            )
        return PolicyDecision(
            Action.RIGHT if horizontal_delta > 0 else Action.LEFT,
            "move_toward_safe_platform",
            **common,
        )
