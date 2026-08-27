from __future__ import annotations

from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from .config import DetectionConfig
from .diagnostics import load_image


class GamePhase(Enum):
    UNKNOWN = "unknown"
    MENU = "menu"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    DIALOG = "dialog"
    NAME_ENTRY = "name_entry"


class GameStateDetector:
    """以使用者校正的中央對話框範本辨識 DIALOG／PLAYING。"""

    def __init__(
        self,
        config: DetectionConfig | None = None,
        template: np.ndarray | None = None,
    ) -> None:
        self.config = config
        self.template = template
        self.last_score = 0.0

    @classmethod
    def from_config(
        cls, config: DetectionConfig, project_root: str | Path
    ) -> "GameStateDetector":
        template_path = Path(config.dialog_template_path)
        if not template_path.is_absolute():
            template_path = Path(project_root) / template_path
        if not template_path.is_file():
            return cls(config, None)
        return cls(config, load_image(template_path))

    def _configured(self) -> bool:
        if self.config is None or self.template is None:
            return False
        cfg = self.config
        positions = (cfg.dialog_roi_left, cfg.dialog_roi_top)
        sizes = (
            cfg.dialog_roi_width,
            cfg.dialog_roi_height,
            cfg.reference_width,
            cfg.reference_height,
        )
        return all(value is not None and value >= 0 for value in positions) and all(
            value is not None and value > 0 for value in sizes
        )

    def detect_with_score(self, frame: np.ndarray) -> tuple[GamePhase, float]:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame 必須是 NumPy ndarray。")
        if not self._configured():
            self.last_score = 0.0
            return GamePhase.UNKNOWN, self.last_score

        assert self.config is not None and self.template is not None
        cfg = self.config
        frame_height, frame_width = frame.shape[:2]
        scale_x = frame_width / int(cfg.reference_width)
        scale_y = frame_height / int(cfg.reference_height)
        left = round(int(cfg.dialog_roi_left) * scale_x)
        top = round(int(cfg.dialog_roi_top) * scale_y)
        width = max(1, round(int(cfg.dialog_roi_width) * scale_x))
        height = max(1, round(int(cfg.dialog_roi_height) * scale_y))
        margin_x = round(cfg.search_margin * scale_x)
        margin_y = round(cfg.search_margin * scale_y)
        search_left = max(0, left - margin_x)
        search_top = max(0, top - margin_y)
        search_right = min(frame_width, left + width + margin_x)
        search_bottom = min(frame_height, top + height + margin_y)
        search = frame[search_top:search_bottom, search_left:search_right]
        template = cv2.resize(self.template, (width, height), interpolation=cv2.INTER_AREA)
        if search.shape[0] < height or search.shape[1] < width:
            self.last_score = 0.0
            return GamePhase.UNKNOWN, self.last_score
        search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(search_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        self.last_score = float(np.max(result))
        phase = (
            GamePhase.DIALOG
            if self.last_score >= cfg.dialog_threshold
            else GamePhase.PLAYING
        )
        return phase, self.last_score

    def detect(self, frame: np.ndarray) -> GamePhase:
        return self.detect_with_score(frame)[0]
