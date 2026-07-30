import pytest

from stair_agent.window_manager import (
    PyWin32Backend,
    Rect,
    WindowError,
    WindowInfo,
    WindowManager,
)


class FakeBackend:
    def __init__(self, windows=None):
        self.windows = windows or []
        self.foreground = 0

    def list_visible(self):
        return self.windows

    def foreground_hwnd(self):
        return self.foreground

    def bring_to_foreground(self, hwnd):
        self.foreground = hwnd
        return True

    def get_window(self, hwnd):
        return next((w for w in self.windows if w.hwnd == hwnd), None)


def window(title="NS Shaft"):
    rect = Rect(10, 20, 640, 480)
    return WindowInfo(123, title, rect, rect)


def test_partial_title_case_insensitive() -> None:
    manager = WindowManager(FakeBackend([window("NS SHAFT Game")]))
    assert manager.find_window("shaft").hwnd == 123


def test_exact_normalized_title_beats_unrelated_longer_title() -> None:
    game = window("NS-SHAFT")
    terminal = WindowInfo(
        456,
        "PowerShell - NS Shaft│小朋友下樓梯",
        game.rect,
        game.client_rect,
    )
    manager = WindowManager(FakeBackend([terminal, game]))
    assert manager.find_window("NS Shaft").title == "NS-SHAFT"


def test_require_ready_rejects_invalid_client_area() -> None:
    item = WindowInfo(123, "NS-SHAFT", Rect(0, 0, 640, 480), Rect(0, 0, 0, 0))
    manager = WindowManager(FakeBackend([item]))
    with pytest.raises(WindowError, match="client area"):
        manager.require_ready("NS-SHAFT")


def test_window_class_prevents_same_title_false_positive() -> None:
    terminal = WindowInfo(
        456,
        "NS-SHAFT",
        Rect(0, 0, 640, 480),
        Rect(0, 0, 634, 431),
        class_name="CASCADIA_HOSTING_WINDOW_CLASS",
    )
    game = WindowInfo(
        123,
        "NS-SHAFT",
        Rect(0, 0, 640, 480),
        Rect(0, 0, 634, 431),
        class_name="NsShaftClass",
    )
    manager = WindowManager(FakeBackend([terminal, game]))
    assert manager.require_ready("NS-SHAFT", "NsShaftClass").hwnd == 123


def test_related_windows_use_same_process_id() -> None:
    rect = Rect(0, 0, 640, 480)
    game = WindowInfo(
        123,
        "NS-SHAFT",
        rect,
        rect,
        class_name="NsShaftClass",
        process_id=42,
    )
    name_dialog = WindowInfo(
        456,
        "輸入名稱",
        Rect(1920, 100, 300, 180),
        Rect(1920, 100, 300, 180),
        class_name="#32770",
        process_id=42,
        owner_hwnd=123,
    )
    unrelated = WindowInfo(
        789,
        "其他程式",
        rect,
        rect,
        process_id=99,
    )
    manager = WindowManager(FakeBackend([game, name_dialog, unrelated]))

    assert manager.related_windows(game) == [name_dialog]
    assert manager.blocking_related_windows(game.hwnd) == [name_dialog]


def test_window_not_found() -> None:
    manager = WindowManager(FakeBackend())
    with pytest.raises(WindowError, match="找不到"):
        manager.find_window("NS Shaft")


class BrokenBackend(FakeBackend):
    def list_visible(self):
        raise WindowError("無法列舉 Windows 視窗")


def test_window_enumeration_error_is_clear() -> None:
    manager = WindowManager(BrokenBackend())
    with pytest.raises(WindowError, match="無法列舉"):
        manager.list_windows()


def test_pywin32_focus_uses_target_only_native_fallback() -> None:
    class FakeGui:
        foreground = 999

        @staticmethod
        def IsIconic(hwnd):
            assert hwnd == 123
            return False

        @staticmethod
        def BringWindowToTop(hwnd):
            assert hwnd == 123

        @staticmethod
        def SetForegroundWindow(hwnd):
            assert hwnd == 123
            # 模擬 Windows 接受呼叫但拒絕實際切換前景。

        @classmethod
        def GetForegroundWindow(cls):
            return cls.foreground

    class FakeUser32:
        calls = []

        @classmethod
        def SwitchToThisWindow(cls, hwnd, alt_tab):
            cls.calls.append((hwnd, alt_tab))
            FakeGui.foreground = hwnd

    backend = PyWin32Backend.__new__(PyWin32Backend)
    backend.win32gui = FakeGui()
    backend.user32 = FakeUser32()

    assert backend.bring_to_foreground(123)
    assert FakeUser32.calls == [(123, True)]
