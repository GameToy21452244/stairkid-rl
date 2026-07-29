from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .hud_detection import HealthUpdate
from .object_detection import PlatformDetection, PlatformKind
from .object_tracking import MotionState, PlayerTrackingState


class GameEvent(Enum):
    NONE = "none"
    LANDED = "landed"
    FLOOR_DESCENDED = "floor_descended"
    SPRING_BOUNCE = "spring_bounce"
    HEALTH_GAINED = "health_gained"
    DAMAGE = "damage"
    SPIKE_DAMAGE = "spike_damage"


@dataclass(frozen=True)
class GameEventDetection:
    event: GameEvent
    source_platform: PlatformDetection | None = None
    health_delta: int | None = None


def describe_event_zh(event: GameEventDetection) -> str:
    names = {
        GameEvent.LANDED: "角色落地",
        GameEvent.FLOOR_DESCENDED: "成功下降至新平台",
        GameEvent.SPRING_BOUNCE: "彈簧向上反彈",
        GameEvent.HEALTH_GAINED: "血量增加",
        GameEvent.DAMAGE: "受到未分類傷害",
        GameEvent.SPIKE_DAMAGE: "尖刺傷害",
    }
    description = names.get(event.event, event.event.value)
    if event.source_platform is not None:
        description += f"({event.source_platform.kind.value})"
    if event.health_delta is not None:
        description += f"(delta={event.health_delta:+d})"
    return description


class SpringBounceDetector:
    """以接近彈簧後轉為上升的連續畫面辨識反彈事件。"""

    def __init__(
        self,
        contact_gap: int = 12,
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


@dataclass(frozen=True)
class LandingDetection:
    landed: bool
    descended: bool
    platform: PlatformDetection | None


class LandingDetector:
    """以落下接近平台後轉為穩定／上升，辨識一次落地與新樓層。"""

    def __init__(
        self,
        contact_gap: int = 6,
        max_wait_frames: int = 4,
    ) -> None:
        self.contact_gap = max(0, contact_gap)
        self.max_wait_frames = max(1, max_wait_frames)
        self._pending_frames = 0
        self._pending_platform: PlatformDetection | None = None
        self._last_landed_track_id: int | None = None

    def reset(self) -> None:
        self._pending_frames = 0
        self._pending_platform = None
        self._last_landed_track_id = None

    def update(self, state: PlayerTrackingState) -> LandingDetection:
        platform = state.nearest_platform_below
        gap = state.platform_vertical_gap
        if (
            state.motion is MotionState.FALLING
            and platform is not None
            and gap is not None
            and gap <= self.contact_gap
        ):
            self._pending_frames = self.max_wait_frames
            self._pending_platform = platform

        if (
            self._pending_frames > 0
            and state.motion in {MotionState.STABLE, MotionState.RISING}
            and self._pending_platform is not None
        ):
            landed = self._pending_platform
            track_id = landed.track_id
            descended = (
                track_id is not None
                and self._last_landed_track_id is not None
                and track_id != self._last_landed_track_id
            )
            if track_id is not None:
                self._last_landed_track_id = track_id
            self._pending_frames = 0
            self._pending_platform = None
            return LandingDetection(True, descended, landed)

        if self._pending_frames > 0:
            self._pending_frames -= 1
            if self._pending_frames == 0:
                self._pending_platform = None
        return LandingDetection(False, False, None)


class GameplayEventDetector:
    """合併落地、彈簧與血量證據；證據不足的傷害維持 generic。"""

    def __init__(
        self,
        landing_contact_gap: int = 6,
        spring_contact_gap: int = 12,
        correlation_frames: int = 5,
    ) -> None:
        self.landing_detector = LandingDetector(
            contact_gap=landing_contact_gap
        )
        self.spring_detector = SpringBounceDetector(
            contact_gap=spring_contact_gap
        )
        self.correlation_frames = max(1, correlation_frames)
        self._recent_platform: PlatformDetection | None = None
        self._recent_frames = 0

    def reset(self) -> None:
        self.landing_detector.reset()
        self.spring_detector.reset()
        self._recent_platform = None
        self._recent_frames = 0

    def update(
        self,
        state: PlayerTrackingState,
        health: HealthUpdate,
    ) -> list[GameEventDetection]:
        events: list[GameEventDetection] = []
        landing = self.landing_detector.update(state)
        if landing.landed:
            events.append(
                GameEventDetection(GameEvent.LANDED, landing.platform)
            )
            if landing.descended:
                events.append(
                    GameEventDetection(
                        GameEvent.FLOOR_DESCENDED,
                        landing.platform,
                    )
                )
            self._recent_platform = landing.platform
            self._recent_frames = self.correlation_frames

        spring = self.spring_detector.update(state)
        if spring.event is GameEvent.SPRING_BOUNCE:
            events.append(spring)

        delta = health.delta
        if delta is not None and delta > 0:
            events.append(
                GameEventDetection(GameEvent.HEALTH_GAINED, health_delta=delta)
            )
        elif delta is not None and delta < 0:
            contact = self._recent_platform
            current = state.nearest_platform_below
            source = (
                contact
                if contact is not None and contact.kind is PlatformKind.SPIKES
                else current
                if current is not None
                and current.kind is PlatformKind.SPIKES
                and state.platform_vertical_gap is not None
                and state.platform_vertical_gap <= self.landing_detector.contact_gap
                else None
            )
            event = (
                GameEvent.SPIKE_DAMAGE
                if source is not None and delta <= -4
                else GameEvent.DAMAGE
            )
            events.append(GameEventDetection(event, source, delta))

        if self._recent_frames > 0:
            self._recent_frames -= 1
            if self._recent_frames == 0:
                self._recent_platform = None
        return events
