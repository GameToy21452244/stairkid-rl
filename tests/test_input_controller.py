import time

import pytest

from stair_agent.config import ControlsConfig, SafetyConfig
from stair_agent.input_controller import (
    Action,
    InputController,
    InputError,
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
        self.related = []

    def is_foreground(self, _hwnd):
        return self.foreground

    def blocking_related_windows(self, _hwnd):
        return self.related


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


def test_release_all_after_exception() -> None:
    controller, backend = make_controller()

    def operation():
        controller.key_down("left")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        controller.run_safely(operation)
    assert controller.held_keys == set()
    assert ("up", "left") in backend.events


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


def test_target_active_requires_foreground_and_no_related_window() -> None:
    controller, _backend = make_controller()

    assert controller.is_target_active()
    controller.window_manager.related = [object()]
    assert not controller.is_target_active()
