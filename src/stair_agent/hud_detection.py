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
