from __future__ import annotations

from typing import Any

from .game_events import GameplayEventDetector
from .game_state import GamePhase
from .hud_detection import FloorCounterTracker, HealthTracker, HudDetector
from .object_detection import ObjectDetector, PlatformKind
from .object_tracking import (
    PlatformStabilizer,
    PlatformTracker,
    PlatformTrackingState,
    PlayerTracker,
)
from .observation import GameObservation, ObservationBuilder


class RealFrameObservationPipeline:
    """Current Real frame -> structured observation path, with no capture/control I/O."""

    def __init__(
        self,
        *,
        object_detector: ObjectDetector,
        hud_detector: HudDetector,
        landing_contact_gap: int,
        spring_contact_gap: int,
        correlation_frames: int,
    ) -> None:
        self.object_detector = object_detector
        self.hud_detector = hud_detector
        self.player_tracker = PlayerTracker()
        self.platform_tracker = PlatformTracker()
        self.platform_stabilizer = PlatformStabilizer(
            persistent_kinds={
                PlatformKind.CONVEYOR,
                PlatformKind.FLIPPING,
                PlatformKind.SPRING,
            },
            persistence_frames=2,
        )
        self.health_tracker = HealthTracker()
        self.floor_tracker = FloorCounterTracker(hud_detector.config)
        self.event_detector = GameplayEventDetector(
            landing_contact_gap=landing_contact_gap,
            spring_contact_gap=spring_contact_gap,
            correlation_frames=correlation_frames,
        )
        self.builder = ObservationBuilder()
        self.last_raw_objects: Any | None = None
        self.last_player_state: Any | None = None
        self.last_platform_state: PlatformTrackingState | None = None

    def reset(self) -> None:
        self.player_tracker.reset()
        self.platform_tracker.reset()
        self.platform_stabilizer.reset()
        self.health_tracker.reset()
        self.floor_tracker.reset()
        self.event_detector.reset()
        self.last_raw_objects = None
        self.last_player_state = None
        self.last_platform_state = None

    @staticmethod
    def empty_observation(timestamp: float, phase: GamePhase) -> GameObservation:
        return GameObservation(
            timestamp=timestamp,
            phase=phase.value,
            player=None,
            health={"segments": 0, "delta": None, "event": "unknown"},
            nearest_platform=None,
            platforms=[],
            platform_scroll_velocity_y=0.0,
            events=[],
            floor={
                "value": None,
                "delta": None,
                "stable": False,
                "confidence": 0.0,
            },
        )

    def observe_frame(
        self,
        frame: Any,
        *,
        timestamp: float,
        phase: GamePhase,
    ) -> GameObservation:
        if phase is not GamePhase.PLAYING:
            self.reset()
            return self.empty_observation(timestamp, phase)

        raw_objects = self.object_detector.detect(frame)
        platform_state = self.platform_tracker.update(raw_objects, timestamp)
        objects = self.platform_stabilizer.update(platform_state.objects)
        platform_state = PlatformTrackingState(
            objects,
            platform_state.scroll_velocity_y,
            platform_state.matched_platforms,
        )
        player_state = self.player_tracker.update(objects, timestamp)
        health = self.hud_detector.detect_health(frame)
        health_update = self.health_tracker.update(health.segments)
        floor_update = self.floor_tracker.update(frame)
        events = self.event_detector.update(
            player_state,
            health_update,
            floor=floor_update,
        )
        self.last_raw_objects = raw_objects
        self.last_player_state = player_state
        self.last_platform_state = platform_state
        return self.builder.build(
            timestamp=timestamp,
            phase=phase,
            player_state=player_state,
            platform_state=platform_state,
            health=health_update,
            events=events,
            floor=floor_update,
        )
