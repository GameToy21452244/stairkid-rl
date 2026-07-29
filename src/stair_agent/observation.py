from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .game_events import GameEventDetection
from .game_state import GamePhase
from .hud_detection import HealthUpdate
from .object_tracking import PlatformTrackingState, PlayerTrackingState


@dataclass(frozen=True)
class GameObservation:
    timestamp: float
    phase: str
    player: dict[str, Any] | None
    health: dict[str, Any]
    nearest_platform: dict[str, Any] | None
    platforms: list[dict[str, Any]]
    platform_scroll_velocity_y: float
    events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "phase": self.phase,
            "player": self.player,
            "health": self.health,
            "nearest_platform": self.nearest_platform,
            "platforms": self.platforms,
            "platform_scroll_velocity_y": self.platform_scroll_velocity_y,
            "events": self.events,
        }


class ObservationBuilder:
    """將畫面辨識結果轉成與 Gymnasium 無關的結構化觀測。"""

    @staticmethod
    def _platform(item) -> dict[str, Any]:
        return {
            "track_id": item.track_id,
            "kind": item.kind.value,
            "confidence": item.confidence,
            "box": {
                "left": item.box.left,
                "top": item.box.top,
                "width": item.box.width,
                "height": item.box.height,
            },
        }

    def build(
        self,
        *,
        timestamp: float,
        phase: GamePhase,
        player_state: PlayerTrackingState,
        platform_state: PlatformTrackingState,
        health: HealthUpdate,
        events: list[GameEventDetection],
    ) -> GameObservation:
        player = None
        if player_state.player is not None:
            center_x, center_y = player_state.player.box.center
            player = {
                "center_x": center_x,
                "center_y": center_y,
                "velocity_x": player_state.velocity_x,
                "velocity_y": player_state.velocity_y,
                "motion": player_state.motion.value,
                "confidence": player_state.player.confidence,
            }
        nearest = (
            None
            if player_state.nearest_platform_below is None
            else {
                **self._platform(player_state.nearest_platform_below),
                "vertical_gap": player_state.platform_vertical_gap,
            }
        )
        event_payloads = [
            {
                "type": event.event.value,
                "source_platform_id": (
                    event.source_platform.track_id
                    if event.source_platform is not None
                    else None
                ),
                "source_platform_kind": (
                    event.source_platform.kind.value
                    if event.source_platform is not None
                    else None
                ),
                "health_delta": event.health_delta,
            }
            for event in events
        ]
        return GameObservation(
            timestamp=timestamp,
            phase=phase.value,
            player=player,
            health={
                "segments": health.segments,
                "delta": health.delta,
                "event": health.event.value,
            },
            nearest_platform=nearest,
            platforms=[
                self._platform(item)
                for item in platform_state.objects.platforms
            ],
            platform_scroll_velocity_y=platform_state.scroll_velocity_y,
            events=event_payloads,
        )


class ObservationJsonlWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")

    def write(self, observation: GameObservation) -> None:
        self._file.write(
            json.dumps(observation.to_dict(), ensure_ascii=False) + "\n"
        )
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "ObservationJsonlWriter":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()
