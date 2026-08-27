from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from stair_agent.config import HudConfig


@dataclass(frozen=True)
class HealthDetection:
    segments: int | None
    confidence: float


class HealthEvent(Enum):
    UNKNOWN = "unknown"
    INITIALIZED = "initialized"
    INCREASED = "increased"
    DECREASED = "decreased"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class HealthUpdate:
    segments: int | None
    delta: int | None
    event: HealthEvent


@dataclass(frozen=True)
class FloorUpdate:
    value: int | None
    delta: int | None
    stable: bool
    confidence: float


class FloorCounterTracker:
    """以校正後的 HUD 數字影像變化追蹤樓層，不依賴 platform track ID。"""

    def __init__(self, config: HudConfig) -> None:
        self.config = config
        self.reset()

    def reset(self) -> None:
        self._value: int | None = None
        self._stable: np.ndarray | None = None
        self._candidate: np.ndarray | None = None
        self._candidate_frames = 0

    def _fingerprint(self, frame: np.ndarray) -> np.ndarray | None:
        if frame.ndim != 3 or frame.shape[2] < 3:
            return None
        roi = (
            self.config.floor_counter_left,
            self.config.floor_counter_top,
            self.config.floor_counter_width,
            self.config.floor_counter_height,
        )
        if any(value is None for value in roi):
            return None
        frame_height, frame_width = frame.shape[:2]
        reference_width = self.config.reference_width or frame_width
        reference_height = self.config.reference_height or frame_height
        if reference_width <= 0 or reference_height <= 0:
            return None
        scale_x = frame_width / reference_width
        scale_y = frame_height / reference_height
        left = round(int(roi[0]) * scale_x)
        top = round(int(roi[1]) * scale_y)
        width = max(1, round(int(roi[2]) * scale_x))
        height = max(1, round(int(roi[3]) * scale_y))
        crop = frame[top : top + height, left : left + width, :3]
        if crop.shape[:2] != (height, width):
            return None
        gray = (
            0.114 * crop[:, :, 0]
            + 0.587 * crop[:, :, 1]
            + 0.299 * crop[:, :, 2]
        )
        return gray >= self.config.floor_binary_threshold

    @staticmethod
    def _difference(first: np.ndarray, second: np.ndarray) -> float:
        if first.shape != second.shape:
            return 1.0
        return float(np.mean(first != second))

    def update(self, frame: np.ndarray) -> FloorUpdate:
        current = self._fingerprint(frame)
        if current is None:
            return FloorUpdate(self._value, None, False, 0.0)
        if self._stable is None or self._stable.shape != current.shape:
            self._stable = current.copy()
            self._candidate = None
            self._candidate_frames = 0
            if self._value is None:
                self._value = self.config.floor_counter_initial_value
            return FloorUpdate(self._value, None, True, 1.0)

        stable_difference = self._difference(current, self._stable)
        if stable_difference <= self.config.floor_stability_ratio_threshold:
            self._candidate = None
            self._candidate_frames = 0
            confidence = max(
                0.0,
                1.0
                - stable_difference
                / max(self.config.floor_change_ratio_threshold, 1e-9),
            )
            return FloorUpdate(self._value, 0, True, confidence)
        if stable_difference < self.config.floor_change_ratio_threshold:
            self._candidate = None
            self._candidate_frames = 0
            return FloorUpdate(self._value, None, False, 0.0)

        if (
            self._candidate is not None
            and self._difference(current, self._candidate)
            <= self.config.floor_stability_ratio_threshold
        ):
            self._candidate_frames += 1
        else:
            self._candidate = current.copy()
            self._candidate_frames = 1
        if (
            self._candidate_frames
            < self.config.floor_change_required_consecutive
        ):
            return FloorUpdate(self._value, None, False, 0.0)

        self._stable = current.copy()
        self._candidate = None
        self._candidate_frames = 0
        self._value = (
            self.config.floor_counter_initial_value
            if self._value is None
            else self._value + 1
        )
        return FloorUpdate(self._value, 1, True, 1.0)


class HudDetector:
    """只從畫面像素估計 LIFE 格數，不讀取遊戲程序資料。"""

    def __init__(self, config: HudConfig) -> None:
        self.config = config

    def detect_health(self, frame: np.ndarray) -> HealthDetection:
        if frame.ndim != 3 or frame.shape[2] < 3:
            return HealthDetection(None, 0.0)
        if self.config.life_left is None or self.config.life_top is None:
            return HealthDetection(None, 0.0)

        frame_height, frame_width = frame.shape[:2]
        reference_width = self.config.reference_width or frame_width
        reference_height = self.config.reference_height or frame_height
        if reference_width <= 0 or reference_height <= 0:
            return HealthDetection(None, 0.0)

        scale_x = frame_width / reference_width
        scale_y = frame_height / reference_height
        left = round(self.config.life_left * scale_x)
        top = round(self.config.life_top * scale_y)
        segment_width = max(1, round(self.config.life_segment_width * scale_x))
        segment_height = max(1, round(self.config.life_segment_height * scale_y))
        pitch = max(1, round(self.config.life_segment_pitch * scale_x))

        ratios: list[float] = []
        for index in range(self.config.life_max_segments):
            segment_left = left + index * pitch
            segment = frame[
                top : top + segment_height,
                segment_left : segment_left + segment_width,
                :3,
            ]
            if segment.shape[:2] != (segment_height, segment_width):
                return HealthDetection(None, 0.0)
            blue, green, red = (
                segment[:, :, 0],
                segment[:, :, 1],
                segment[:, :, 2],
            )
            filled = (
                (red >= self.config.life_red_min)
                & (green >= self.config.life_green_min)
                & (blue <= self.config.life_blue_max)
            )
            ratios.append(float(np.count_nonzero(filled)) / filled.size)

        occupied = [
            ratio >= self.config.life_filled_ratio for ratio in ratios
        ]
        segments = 0
        for is_filled in occupied:
            if not is_filled:
                break
            segments += 1

        # LIFE 應由左至右連續；中間空格後又亮起通常代表畫面/座標不可靠。
        if any(occupied[segments:]):
            return HealthDetection(None, 0.0)
        distance = [
            abs(ratio - self.config.life_filled_ratio) for ratio in ratios
        ]
        confidence = min(1.0, min(distance) / max(self.config.life_filled_ratio, 1e-6))
        return HealthDetection(segments, confidence)


class HealthTracker:
    """回報相鄰有效觀測的原始格數差，不猜測受傷或下樓事件。"""

    def __init__(self) -> None:
        self._previous: int | None = None

    def update(self, segments: int | None) -> HealthUpdate:
        if segments is None:
            return HealthUpdate(None, None, HealthEvent.UNKNOWN)
        if self._previous is None:
            self._previous = segments
            return HealthUpdate(segments, None, HealthEvent.INITIALIZED)

        delta = segments - self._previous
        self._previous = segments
        if delta > 0:
            event = HealthEvent.INCREASED
        elif delta < 0:
            event = HealthEvent.DECREASED
        else:
            event = HealthEvent.UNCHANGED
        return HealthUpdate(segments, delta, event)

    def reset(self) -> None:
        self._previous = None
