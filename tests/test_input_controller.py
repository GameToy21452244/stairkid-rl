import time
import sys
from types import SimpleNamespace

import pytest

from stair_agent.config import ControlsConfig, SafetyConfig
from stair_agent.input_controller import (
    Action,
    InputController,
    InputError,
    PyAutoGUIBackend,
    SafetyMonitor,
)


class FakeBackend:
    def __init__(self):
        self.events = []

    def key_down(self, key):
        self.events.append(("down", key))

    def key_up(self, key):
        self.events.append(("up", key))

    def press(self, key):
        self.events.append(("press", key))


class FakeManager:
    def __init__(self):
        self.foreground = True
        self.foreground_handle = 1
        self.related = []
        self.related_check_count = 0

    def is_foreground(self, _hwnd):
        return self.foreground

    def blocking_related_windows(self, _hwnd):
        self.related_check_count += 1
        return self.related

    def foreground_hwnd(self):
        return self.foreground_handle

    def find_name_entry_dialog(self, _hwnd):
        if len(self.related) != 1:
            return None
        candidate = self.related[0]
        return candidate if getattr(candidate, "is_name_entry", False) else None


def make_controller():
    backend = FakeBackend()
    controller = InputController(
        ControlsConfig(), SafetyConfig(), FakeManager(), 1, backend
    )
    return controller, backend


def test_left_right_are_mutually_exclusive() -> None:
    controller, backend = make_controller()
    controller.apply(Action.LEFT)
    controller.apply(Action.RIGHT)
    assert backend.events[:3] == [
        ("down", "left"),
        ("up", "left"),
        ("down", "right"),
    ]
    assert controller.held_keys == {"right"}


def test_repeated_same_direction_does_not_resend_key_down() -> None:
    controller, backend = make_controller()

    controller.apply(Action.LEFT)
    controller.apply(Action.LEFT)

    assert backend.events == [("down", "left")]
    assert controller.held_keys == {"left"}


def test_release_all_after_exception() -> None:
    controller, backend = make_controller()

    def operation():
        controller.key_down("left")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        controller.run_safely(operation)
    assert controller.held_keys == set()
    assert ("up", "left") in backend.events


def test_release_all_does_not_emit_untracked_direction_keyups() -> None:
    controller, backend = make_controller()

    controller.release_all()

    assert backend.events == []


def test_failed_key_down_attempts_key_up_and_clears_tracking() -> None:
    class FailingBackend(FakeBackend):
        def key_down(self, key):
            self.events.append(("down", key))
            raise RuntimeError("backend failed")

    backend = FailingBackend()
    controller = InputController(
        ControlsConfig(),
        SafetyConfig(),
        FakeManager(),
        1,
        backend,
    )

    with pytest.raises(RuntimeError, match="backend failed"):
        controller.key_down("left")

    assert backend.events == [("down", "left"), ("up", "left")]
    assert controller.held_keys == set()


def test_emergency_stop_state() -> None:
    controller, _backend = make_controller()
    controller.key_down("left")
    controller.emergency_stop()
    assert controller.emergency_stopped
    assert not controller.held_keys


def test_f8_monitor_uses_mock_checker() -> None:
    controller, _backend = make_controller()
    controller.key_down("left")
    monitor = SafetyMonitor(controller, "f8", key_checker=lambda _key: True)
    monitor.start()
    time.sleep(0.05)
    monitor.stop()
    assert controller.emergency_stopped
    assert not controller.held_keys


def test_related_game_window_blocks_input_and_releases() -> None:
    controller, backend = make_controller()
    controller.window_manager.related = [object()]

    with pytest.raises(InputError, match="其他可見視窗"):
        controller.apply(Action.LEFT)

    assert controller.held_keys == set()
    assert ("down", "left") not in backend.events


def test_verified_name_entry_dialog_can_only_press_enter_then_resume() -> None:
    controller, backend = make_controller()
    dialog = SimpleNamespace(hwnd=456, is_name_entry=True)
    controller.window_manager.related = [dialog]
    controller.window_manager.foreground_handle = 456
    controller.refresh_related_window_state()

    detected = controller.dismiss_verified_name_entry_dialog()

    assert detected is dialog
    assert backend.events == [("press", "enter")]
    assert controller.related_window_stopped

    controller.window_manager.related = []
    controller.window_manager.foreground_handle = 1
    controller.window_manager.foreground = True

    assert controller.resume_after_related_window()
    assert not controller.related_window_stopped


def test_unrecognized_related_dialog_never_receives_enter() -> None:
    controller, backend = make_controller()
    controller.window_manager.related = [
        SimpleNamespace(hwnd=456, is_name_entry=False)
    ]
    controller.window_manager.foreground_handle = 456
    controller.refresh_related_window_state()

    assert controller.dismiss_verified_name_entry_dialog() is None
    assert backend.events == []


def test_target_active_requires_foreground_and_no_related_window() -> None:
    controller, _backend = make_controller()

    assert controller.is_target_active()
    controller.window_manager.related = [object()]
    controller.refresh_related_window_state()
    assert not controller.is_target_active()


def test_related_window_cache_avoids_enumerating_every_action() -> None:
    controller, _backend = make_controller()

    controller.refresh_related_window_state()
    controller.apply(Action.LEFT)
    controller.release_all()
    controller.apply(Action.RIGHT)

    assert controller.window_manager.related_check_count == 1


def test_safety_monitor_stops_when_related_window_appears() -> None:
    controller, _backend = make_controller()
    monitor = SafetyMonitor(
        controller,
        "f8",
        key_checker=lambda _key: False,
        interval=0.005,
        related_window_interval=0.01,
    )
    monitor.start()
    controller.key_down("left")
    controller.window_manager.related = [object()]
    time.sleep(0.05)
    monitor.stop()

    assert controller.related_window_stopped
    assert not controller.held_keys


def test_pyautogui_backend_skips_only_generic_pause_and_keeps_failsafe(
    monkeypatch,
) -> None:
    calls = []
    fake = SimpleNamespace(
        FAILSAFE=True,
        keyDown=lambda key, **kwargs: calls.append(("down", key, kwargs)),
        keyUp=lambda key, **kwargs: calls.append(("up", key, kwargs)),
        press=lambda key, **kwargs: calls.append(("press", key, kwargs)),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    backend = PyAutoGUIBackend()

    backend.key_down("left")
    backend.key_up("left")
    backend.press("enter")

    assert calls == [
        ("down", "left", {"_pause": False}),
        ("up", "left", {"_pause": False}),
        ("press", "enter", {"_pause": False}),
    ]
    assert fake.FAILSAFE is True
