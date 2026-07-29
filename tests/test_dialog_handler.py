import numpy as np
import pytest

from stair_agent.dialog_handler import (
    DialogActionError,
    DialogActionHandler,
    DialogActionOutcome,
    StableObservation,
)
from stair_agent.game_state import GamePhase


class SequenceDetector:
    def __init__(self, phases):
        self.phases = iter(phases)

    def detect_with_score(self, _frame):
        phase = next(self.phases)
        score = 0.95 if phase is GamePhase.DIALOG else 0.05
        return phase, score


class FakeController:
    def __init__(self):
        self.taps = []
        self.release_count = 0

    def tap(self, key, duration_ms=None):
        self.taps.append((key, duration_ms))

    def release_all(self):
        self.release_count += 1


def frame_source(frames):
    iterator = iter(frames)
    return lambda: next(iterator)


def test_dialog_to_playing_sends_exactly_one_enter() -> None:
    frames = [np.zeros((20, 30, 3), dtype=np.uint8) for _ in range(4)]
    detector = SequenceDetector(
        [
            GamePhase.DIALOG,
            GamePhase.DIALOG,
            GamePhase.PLAYING,
            GamePhase.PLAYING,
        ]
    )
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(frames),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=4,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.outcome is DialogActionOutcome.PLAYING
    assert controller.taps == [("enter", 200)]
    assert controller.release_count >= 2


def test_non_dialog_never_sends_enter() -> None:
    frames = [np.zeros((20, 30, 3), dtype=np.uint8) for _ in range(2)]
    detector = SequenceDetector([GamePhase.PLAYING, GamePhase.PLAYING])
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(frames),
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(DialogActionError, match="不是 DIALOG"):
        handler.execute_once()

    assert controller.taps == []
    assert controller.release_count >= 1


def test_changed_dialog_still_does_not_press_twice() -> None:
    before = np.zeros((20, 30, 3), dtype=np.uint8)
    after = np.full((20, 30, 3), 255, dtype=np.uint8)
    detector = SequenceDetector([GamePhase.DIALOG] * 4)
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source([before, before, after, after]),
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        dialog_change_threshold=0.05,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.outcome is DialogActionOutcome.DIALOG_CHANGED
    assert controller.taps == [("enter", None)]
    assert result.frame_change > 0.9


def test_release_all_runs_when_observation_fails_after_enter() -> None:
    before = np.zeros((20, 30, 3), dtype=np.uint8)
    detector = SequenceDetector([GamePhase.DIALOG, GamePhase.DIALOG])
    controller = FakeController()
    calls = iter([before, before])

    def broken_source():
        try:
            return next(calls)
        except StopIteration:
            raise RuntimeError("capture failed")

    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        broken_source,
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(RuntimeError, match="capture failed"):
        handler.execute_once()

    assert controller.taps == [("enter", None)]
    assert controller.release_count >= 2


def test_execute_can_reuse_previously_confirmed_dialog() -> None:
    before_frame = np.zeros((20, 30, 3), dtype=np.uint8)
    after_frames = [
        np.ones((20, 30, 3), dtype=np.uint8),
        np.ones((20, 30, 3), dtype=np.uint8),
    ]
    detector = SequenceDetector([GamePhase.PLAYING, GamePhase.PLAYING])
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(after_frames),
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )
    confirmed = StableObservation(
        GamePhase.DIALOG,
        0.99,
        before_frame,
        3,
    )

    result = handler.execute_once(confirmed)

    assert result.before is confirmed
    assert result.outcome is DialogActionOutcome.PLAYING
    assert controller.taps == [("enter", None)]
