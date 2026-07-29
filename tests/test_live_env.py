import pytest

from stair_agent.input_controller import Action
from stair_agent.live_env import LiveGameAdapter


class FakeController:
    def __init__(self):
        self.applied = []
        self.release_count = 0

    def apply(self, action):
        self.applied.append(action)

    def release_all(self):
        self.release_count += 1


class FakeResource:
    def __init__(self):
        self.calls = 0

    def reset(self):
        self.calls += 1

    def close(self):
        self.calls += 1

    def stop(self):
        self.calls += 1


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
