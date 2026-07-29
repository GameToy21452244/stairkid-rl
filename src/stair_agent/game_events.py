from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .object_detection import PlatformDetection, PlatformKind
from .object_tracking import MotionState, PlayerTrackingState


class GameEvent(Enum):
    NONE = "none"
    SPRING_BOUNCE = "spring_bounce"


@dataclass(frozen=True)
class GameEventDetection:
    event: GameEvent
    source_platform: PlatformDetection | None = None


class SpringBounceDetector:
    """以接近彈簧後轉為上升的連續畫面辨識反彈事件。"""

    def __init__(
        self,
        contact_gap: int = 6,
        max_wait_frames: int = 5,
        cooldown_frames: int = 5,
    ) -> None:
        self.contact_gap = max(0, contact_gap)
        self.max_wait_frames = max(1, max_wait_frames)
        self.cooldown_frames = max(0, cooldown_frames)
        self._pending_frames = 0
        self._pending_platform: PlatformDetection | None = None
        self._cooldown = 0

    def reset(self) -> None:
        self._pending_frames = 0
        self._pending_platform = None
        self._cooldown = 0

    def update(self, state: PlayerTrackingState) -> GameEventDetection:
        if self._cooldown > 0:
            self._cooldown -= 1
            return GameEventDetection(GameEvent.NONE)

        platform = state.nearest_platform_below
        gap = state.platform_vertical_gap
        touching_spring = (
            platform is not None
            and platform.kind is PlatformKind.SPRING
            and gap is not None
            and gap <= self.contact_gap
        )
        if touching_spring and state.motion in {
            MotionState.FALLING,
            MotionState.STABLE,
        }:
            self._pending_frames = self.max_wait_frames
            self._pending_platform = platform

        if (
            self._pending_frames > 0
            and state.motion is MotionState.RISING
        ):
            source = self._pending_platform
            self._pending_frames = 0
            self._pending_platform = None
            self._cooldown = self.cooldown_frames
            return GameEventDetection(GameEvent.SPRING_BOUNCE, source)

        if self._pending_frames > 0:
            self._pending_frames -= 1
            if self._pending_frames == 0:
                self._pending_platform = None
        return GameEventDetection(GameEvent.NONE)
