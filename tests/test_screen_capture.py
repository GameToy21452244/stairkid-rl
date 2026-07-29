import numpy as np
import pytest

from stair_agent.config import CaptureConfig
from stair_agent.screen_capture import (
    CaptureError,
    ScreenCapture,
    process_frame,
    resolve_capture_region,
    validate_region,
)
from stair_agent.window_manager import Rect, WindowInfo


class FakeGrabber:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def grab(self, monitor):
        self.calls += 1
        return np.zeros((monitor["height"], monitor["width"], 4), dtype=np.uint8)

    def close(self):
        self.closed = True


class FakeManager:
    def refresh(self, _hwnd):
        rect = Rect(100, 200, 640, 480)
        return WindowInfo(1, "game", rect, rect)


def test_invalid_region() -> None:
    with pytest.raises(CaptureError):
        validate_region(Rect(0, 0, 0, 10))


def test_client_region_is_relative() -> None:
    rect = Rect(100, 200, 640, 480)
    window = WindowInfo(1, "game", rect, rect)
    config = CaptureConfig(left=5, top=10, width=300, height=400)
    assert resolve_capture_region(config, window) == Rect(105, 210, 300, 400)


def test_resize_dimensions() -> None:
    config = CaptureConfig(resize_width=320, resize_height=480)
    frame = process_frame(np.zeros((100, 200, 3), dtype=np.uint8), config)
    assert frame.shape == (480, 320, 3)


def test_single_and_continuous_capture() -> None:
    fake = FakeGrabber()
    capture = ScreenCapture(
        CaptureConfig(resize_width=32, resize_height=48),
        FakeManager(),
        1,
        grabber_factory=lambda: fake,
    )
    with capture:
        assert capture.capture().shape == (48, 32, 3)
        assert capture.capture().shape == (48, 32, 3)
    assert fake.calls == 2
    assert fake.closed
