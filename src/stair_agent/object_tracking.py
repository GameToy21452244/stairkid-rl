from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median

from .object_detection import (
    GameObjects,
    PlatformDetection,
    PlatformKind,
    PlayerDetection,
)


class MotionState(Enum):
    UNKNOWN = "unknown"
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


@dataclass(frozen=True)
class PlayerTrackingState:
    player: PlayerDetection | None
    velocity_x: float
    velocity_y: float
    motion: MotionState
    nearest_platform_below: PlatformDetection | None
    platform_vertical_gap: int | None


class PlayerTracker:
    """從連續偵測計算角色速度與下方最近的水平重疊平台。"""

    def __init__(self, motion_threshold: float = 5.0) -> None:
        self.motion_threshold = max(0.0, motion_threshold)
        self._previous_player: PlayerDetection | None = None
        self._previous_timestamp: float | None = None

    @staticmethod
    def _nearest_platform(
        objects: GameObjects,
    ) -> tuple[PlatformDetection | None, int | None]:
        if objects.player is None:
            return None, None
        player = objects.player.box
        player_right = player.left + player.width
        player_bottom = player.top + player.height
        candidates: list[tuple[int, PlatformDetection]] = []
        for platform in objects.platforms:
            box = platform.box
            platform_right = box.left + box.width
            overlap = min(player_right, platform_right) - max(player.left, box.left)
            gap = box.top - player_bottom
            if overlap > 0 and gap >= -3:
                candidates.append((max(0, gap), platform))
        if not candidates:
            return None, None
        gap, platform = min(candidates, key=lambda item: item[0])
        return platform, gap

    def reset(self) -> None:
        self._previous_player = None
        self._previous_timestamp = None

    def update(
        self,
        objects: GameObjects,
        timestamp: float,
    ) -> PlayerTrackingState:
        nearest, gap = self._nearest_platform(objects)
        if objects.player is None:
            self.reset()
            return PlayerTrackingState(
                None,
                0.0,
                0.0,
                MotionState.UNKNOWN,
                nearest,
                gap,
            )

        velocity_x = 0.0
        velocity_y = 0.0
        motion = MotionState.UNKNOWN
        if (
            self._previous_player is not None
            and self._previous_timestamp is not None
            and timestamp > self._previous_timestamp
        ):
            elapsed = timestamp - self._previous_timestamp
            current_x, current_y = objects.player.box.center
            previous_x, previous_y = self._previous_player.box.center
            velocity_x = (current_x - previous_x) / elapsed
            velocity_y = (current_y - previous_y) / elapsed
            if velocity_y > self.motion_threshold:
                motion = MotionState.FALLING
            elif velocity_y < -self.motion_threshold:
                motion = MotionState.RISING
            else:
                motion = MotionState.STABLE
        self._previous_player = objects.player
        self._previous_timestamp = timestamp
        return PlayerTrackingState(
            objects.player,
            velocity_x,
            velocity_y,
            motion,
            nearest,
            gap,
        )


@dataclass
class _PlatformTrack:
    detection: PlatformDetection
    missed_frames: int = 0


class PlatformStabilizer:
    """短暫保留動畫平台，避免單幀模板分數波動造成框線閃爍。"""

    def __init__(
        self,
        persistent_kinds: set[PlatformKind],
        persistence_frames: int = 2,
        match_distance: float = 20.0,
    ) -> None:
        self.persistent_kinds = set(persistent_kinds)
        self.persistence_frames = max(0, persistence_frames)
        self.match_distance = max(0.0, match_distance)
        self._tracks: list[_PlatformTrack] = []

    @staticmethod
    def _center_distance(
        first: PlatformDetection,
        second: PlatformDetection,
    ) -> float:
        first_x, first_y = first.box.center
        second_x, second_y = second.box.center
        return ((first_x - second_x) ** 2 + (first_y - second_y) ** 2) ** 0.5

    def reset(self) -> None:
        self._tracks.clear()

    def update(self, objects: GameObjects) -> GameObjects:
        stable = [
            item
            for item in objects.platforms
            if item.kind not in self.persistent_kinds
        ]
        current = [
            item
            for item in objects.platforms
            if item.kind in self.persistent_kinds
        ]
        unmatched_tracks = set(range(len(self._tracks)))
        next_tracks: list[_PlatformTrack] = []
        for detection in current:
            candidates = [
                index
                for index in unmatched_tracks
                if self._tracks[index].detection.kind is detection.kind
                and self._center_distance(
                    self._tracks[index].detection,
                    detection,
                )
                <= self.match_distance
            ]
            if candidates:
                best = min(
                    candidates,
                    key=lambda index: self._center_distance(
                        self._tracks[index].detection,
                        detection,
                    ),
                )
                unmatched_tracks.remove(best)
            next_tracks.append(_PlatformTrack(detection))
            stable.append(detection)

        for index in unmatched_tracks:
            track = self._tracks[index]
            track.missed_frames += 1
            if track.missed_frames <= self.persistence_frames:
                next_tracks.append(track)
                stable.append(track.detection)
        self._tracks = next_tracks
        stable.sort(key=lambda item: (item.box.top, item.box.left))
        return GameObjects(objects.player, stable, objects.playfield)


@dataclass(frozen=True)
class PlatformTrackingState:
    objects: GameObjects
    scroll_velocity_y: float
    matched_platforms: int


@dataclass
class _IdentityTrack:
    detection: PlatformDetection
    timestamp: float
    missed_frames: int = 0


class PlatformTracker:
    """替平台配置跨幀 ID，並以配對平台的中位位移估計畫面捲動速度。"""

    def __init__(
        self,
        match_distance: float = 24.0,
        max_missed_frames: int = 2,
    ) -> None:
        self.match_distance = max(0.0, match_distance)
        self.max_missed_frames = max(0, max_missed_frames)
        self._tracks: dict[int, _IdentityTrack] = {}
        self._next_id = 1

    @staticmethod
    def _distance(
        first: PlatformDetection,
        second: PlatformDetection,
    ) -> float:
        first_x, first_y = first.box.center
        second_x, second_y = second.box.center
        return ((first_x - second_x) ** 2 + (first_y - second_y) ** 2) ** 0.5

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

    def update(
        self,
        objects: GameObjects,
        timestamp: float,
    ) -> PlatformTrackingState:
        available = set(self._tracks)
        next_tracks: dict[int, _IdentityTrack] = {}
        tracked_platforms: list[PlatformDetection] = []
        vertical_velocities: list[float] = []

        for detection in objects.platforms:
            candidates = [
                track_id
                for track_id in available
                if self._tracks[track_id].detection.kind is detection.kind
                and self._distance(
                    self._tracks[track_id].detection,
                    detection,
                )
                <= self.match_distance
            ]
            if candidates:
                track_id = min(
                    candidates,
                    key=lambda item: self._distance(
                        self._tracks[item].detection,
                        detection,
                    ),
                )
                previous = self._tracks[track_id].detection
                track_elapsed = timestamp - self._tracks[track_id].timestamp
                available.remove(track_id)
                if track_elapsed > 0:
                    vertical_velocities.append(
                        (detection.box.top - previous.box.top) / track_elapsed
                    )
            else:
                track_id = self._next_id
                self._next_id += 1

            tracked = PlatformDetection(
                detection.box,
                detection.kind,
                detection.confidence,
                track_id,
            )
            tracked_platforms.append(tracked)
            next_tracks[track_id] = _IdentityTrack(tracked, timestamp)

        for track_id in available:
            track = self._tracks[track_id]
            track.missed_frames += 1
            if track.missed_frames <= self.max_missed_frames:
                next_tracks[track_id] = track

        self._tracks = next_tracks
        tracked_objects = GameObjects(
            objects.player,
            tracked_platforms,
            objects.playfield,
        )
        scroll_velocity = (
            float(median(vertical_velocities))
            if vertical_velocities
            else 0.0
        )
        return PlatformTrackingState(
            tracked_objects,
            scroll_velocity,
            len(vertical_velocities),
        )
