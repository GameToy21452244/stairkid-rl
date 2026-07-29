from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import cv2
import mss
import numpy as np

from .config import CaptureConfig
from .window_manager import Rect, WindowInfo, WindowManager


class CaptureError(RuntimeError):
    """畫面擷取失敗。"""


def validate_region(region: Rect) -> None:
    if not region.valid:
        raise CaptureError(
            f"擷取區域無效：left={region.left}, top={region.top}, "
            f"width={region.width}, height={region.height}"
        )


def resolve_capture_region(config: CaptureConfig, window: WindowInfo | None) -> Rect:
    if config.mode == "client_area":
        if window is None:
            raise CaptureError("client_area 模式需要有效的遊戲視窗。")
        base = window.client_rect
        left_offset = config.left or 0
        top_offset = config.top or 0
        width = config.width if config.width is not None else base.width - left_offset
        height = config.height if config.height is not None else base.height - top_offset
        region = Rect(base.left + left_offset, base.top + top_offset, width, height)
        if left_offset < 0 or top_offset < 0:
            raise CaptureError("client_area 的 left/top 必須是非負相對位移。")
        if left_offset + width > base.width or top_offset + height > base.height:
            raise CaptureError("校正後擷取區域超出遊戲 client area。")
    else:
        values = (config.left, config.top, config.width, config.height)
        if any(value is None for value in values):
            raise CaptureError("manual 模式必須設定 left、top、width、height。")
        region = Rect(*values)  # type: ignore[arg-type]
    validate_region(region)
    return region


def process_frame(frame: np.ndarray, config: CaptureConfig) -> np.ndarray:
    if config.resize_width and config.resize_height:
        frame = cv2.resize(
            frame,
            (config.resize_width, config.resize_height),
            interpolation=cv2.INTER_AREA,
        )
    if config.grayscale:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame


class ScreenCapture:
    def __init__(
        self,
        config: CaptureConfig,
        window_manager: WindowManager | None = None,
        hwnd: int | None = None,
        grabber_factory: Callable[[], Any] = mss.mss,
    ) -> None:
        self.config = config
        self.window_manager = window_manager
        self.hwnd = hwnd
        self._grabber_factory = grabber_factory
        self._grabber: Any = None
        self._last_capture: float | None = None
        self.fps = 0.0
        self.last_region: Rect | None = None

    def __enter__(self) -> "ScreenCapture":
        self.open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def open(self) -> None:
        if self._grabber is None:
            self._grabber = self._grabber_factory()

    def close(self) -> None:
        if self._grabber is not None:
            close = getattr(self._grabber, "close", None)
            if close:
                close()
            self._grabber = None

    def _window(self) -> WindowInfo | None:
        if self.config.mode != "client_area":
            return None
        if self.window_manager is None or self.hwnd is None:
            raise CaptureError("缺少目標視窗，無法使用 client_area 模式。")
        try:
            return self.window_manager.refresh(self.hwnd)
        except Exception as exc:
            raise CaptureError(str(exc)) from exc

    def capture(self) -> np.ndarray:
        self.open()
        region = resolve_capture_region(self.config, self._window())
        monitor = {
            "left": region.left,
            "top": region.top,
            "width": region.width,
            "height": region.height,
        }
        try:
            raw = np.asarray(self._grabber.grab(monitor))
        except Exception as exc:
            raise CaptureError(f"擷取畫面失敗：{exc}") from exc
        if raw.size == 0 or raw.ndim != 3 or raw.shape[2] < 3:
            raise CaptureError("擷取結果為空或格式無效。")
        frame = process_frame(raw[:, :, :3].copy(), self.config)
        now = time.perf_counter()
        if self._last_capture is not None:
            elapsed = now - self._last_capture
            if elapsed > 0:
                instant = 1.0 / elapsed
                self.fps = instant if self.fps == 0 else self.fps * 0.85 + instant * 0.15
        self._last_capture = now
        self.last_region = region
        return frame
