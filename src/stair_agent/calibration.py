from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2

from .config import AppConfig
from .diagnostics import annotate_frame, prepare_preview_window, save_image
from .screen_capture import ScreenCapture
from .window_manager import WindowManager


@dataclass
class CalibrationResult:
    left: int
    top: int
    width: int
    height: int


class CaptureCalibrator:
    def __init__(
        self,
        config: AppConfig,
        manager: WindowManager,
        hwnd: int,
        config_path: Path,
        capture_dir: Path,
    ) -> None:
        self.config = config
        self.manager = manager
        self.hwnd = hwnd
        self.config_path = config_path
        self.capture_dir = capture_dir

    def _normalize(self) -> CalibrationResult:
        client = self.manager.refresh(self.hwnd).client_rect
        cap = self.config.capture
        left = max(0, min(cap.left or 0, client.width - 1))
        top = max(0, min(cap.top or 0, client.height - 1))
        width = cap.width if cap.width is not None else client.width - left
        height = cap.height if cap.height is not None else client.height - top
        width = max(1, min(width, client.width - left))
        height = max(1, min(height, client.height - top))
        cap.left, cap.top, cap.width, cap.height = left, top, width, height
        return CalibrationResult(left, top, width, height)

    def adjust(self, key: int, step: int = 1) -> bool:
        result = self._normalize()
        changes = {
            ord("h"): ("left", -step),
            ord("l"): ("left", step),
            ord("k"): ("top", -step),
            ord("j"): ("top", step),
            ord("a"): ("width", -step),
            ord("d"): ("width", step),
            ord("w"): ("height", step),
            ord("x"): ("height", -step),
        }
        if key not in changes:
            return False
        name, delta = changes[key]
        setattr(self.config.capture, name, getattr(result, name) + delta)
        self._normalize()
        return True

    def run(self) -> None:
        self._normalize()
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        window_name = "NS-SHAFT 擷取校正"
        help_text = "H/L:left  K/J:top  A/D:width  W/X:height  S:save  Enter:apply  Esc:exit"
        target = self.manager.require_ready(
            self.config.game.window_title_contains,
            self.config.game.window_class_name,
        )
        prepare_preview_window(window_name, target)
        self.manager.focus(self.hwnd)
        with ScreenCapture(
            self.config.capture, self.manager, self.hwnd
        ) as capture:
            while True:
                frame = capture.capture()
                preview = annotate_frame(
                    frame,
                    capture.fps if self.config.diagnostics.show_fps else None,
                    self.config.diagnostics.draw_capture_border,
                    help_text,
                )
                cv2.imshow(window_name, preview)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key in (ord("s"), ord("S")):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    path = self.capture_dir / f"calibration_{timestamp}.png"
                    save_image(path, frame)
                    print(f"已儲存：{path}")
                elif key in (13, 10):
                    self.config.save(self.config_path)
                    print(f"校正結果已寫入：{self.config_path}")
                    break
                else:
                    self.adjust(key)
        cv2.destroyAllWindows()
