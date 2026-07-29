import pytest

from stair_agent.config import DetectionConfig
from stair_agent.game_state import GamePhase
from stair_agent.input_controller import Action
from stair_agent.live_env import (
    LiveGameAdapter,
    build_dialog_focus_guard,
)


class FakeController:
    def __init__(self):
        self.applied = []
        self.release_count = 0
        self.emergency_stopped = False
        self.hwnd = 123
        self.window_manager = FakeWindowManager()

    def apply(self, action):
        self.applied.append(action)

    def release_all(self):
        self.release_count += 1

    def is_target_active(self):
        return self.window_manager.is_foreground(
            self.hwnd
        ) and not self.window_manager.blocking_related_windows(self.hwnd)


class FakeWindowManager:
    def is_foreground(self, hwnd):
        return hwnd == 123

    def blocking_related_windows(self, _hwnd):
        return []


class FakeResource:
    def __init__(self):
        self.calls = 0

    def reset(self):
        self.calls += 1

    def close(self):
        self.calls += 1

    def stop(self):
        self.calls += 1


def test_dialog_focus_guard_requires_calibrated_buttons() -> None:
    with pytest.raises(RuntimeError, match="避免誤選雙人模式"):
        build_dialog_focus_guard(DetectionConfig())


def test_dialog_focus_guard_builds_from_calibrated_config() -> None:
    guard = build_dialog_focus_guard(
        DetectionConfig(
            reference_width=634,
            reference_height=431,
            menu_start_button_left=381,
            menu_start_button_top=297,
            menu_start_button_width=81,
            menu_start_button_height=21,
            menu_two_player_button_left=289,
            menu_two_player_button_top=297,
            menu_two_player_button_width=81,
            menu_two_player_button_height=21,
        )
    )

    assert guard.start_button_rect == (381, 297, 81, 21)


def test_live_adapter_sends_one_bounded_action() -> None:
    controller = FakeController()
    observed = object()
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: observed,
        reset_pipeline=lambda: None,
        action_duration_ms=80,
        sleeper=lambda seconds: None,
    )

    result = adapter.step(Action.LEFT)

    assert result is observed
    assert controller.applied == [Action.LEFT]
    assert controller.release_count == 1


def test_live_adapter_releases_if_capture_fails() -> None:
    controller = FakeController()

    def broken_observe():
        raise RuntimeError("capture failed")

    adapter = LiveGameAdapter(
        controller=controller,
        observe=broken_observe,
        reset_pipeline=lambda: None,
        action_duration_ms=80,
        sleeper=lambda seconds: None,
    )

    with pytest.raises(RuntimeError, match="capture failed"):
        adapter.step(Action.RIGHT)

    assert controller.release_count == 1


def test_live_adapter_does_not_send_direction_after_dialog_appears() -> None:
    controller = FakeController()
    terminal = object()
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: terminal,
        reset_pipeline=lambda: None,
        action_duration_ms=80,
        action_phase_probe=lambda: GamePhase.DIALOG,
        sleeper=lambda seconds: None,
    )

    result = adapter.step(Action.LEFT)

    assert result is terminal
    assert controller.applied == []
    assert controller.release_count >= 1


def test_live_adapter_sends_direction_when_phase_probe_is_playing() -> None:
    controller = FakeController()
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: object(),
        reset_pipeline=lambda: None,
        action_duration_ms=80,
        action_phase_probe=lambda: GamePhase.PLAYING,
        sleeper=lambda seconds: None,
    )

    adapter.step(Action.RIGHT)

    assert controller.applied == [Action.RIGHT]


def test_live_adapter_reset_and_close_clean_everything() -> None:
    controller = FakeController()
    capture = FakeResource()
    monitor = FakeResource()
    reset_calls = []
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: object(),
        reset_pipeline=lambda: reset_calls.append(True),
        action_duration_ms=80,
        capture=capture,
        monitor=monitor,
        sleeper=lambda seconds: None,
    )

    adapter.reset()
    adapter.close()

    assert reset_calls == [True]
    assert controller.release_count >= 2
    assert monitor.calls == 1
    assert capture.calls == 1


def test_live_adapter_exposes_safety_state() -> None:
    controller = FakeController()
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: object(),
        reset_pipeline=lambda: None,
        action_duration_ms=80,
        sleeper=lambda seconds: None,
    )

    assert adapter.is_foreground()
    assert not adapter.emergency_stopped
    controller.emergency_stopped = True
    assert adapter.emergency_stopped


def test_live_adapter_uses_optional_episode_resetter() -> None:
    controller = FakeController()
    resetter = FakeResource()
    expected = object()
    resetter.reset = lambda: expected
    reset_pipeline_calls = []
    adapter = LiveGameAdapter(
        controller=controller,
        observe=lambda: object(),
        reset_pipeline=lambda: reset_pipeline_calls.append(True),
        action_duration_ms=80,
        episode_resetter=resetter,
        sleeper=lambda seconds: None,
    )

    result = adapter.reset()

    assert result is expected
    assert reset_pipeline_calls == []
