import numpy as np
import pytest

from stair_agent.dialog_handler import (
    DialogActionError,
    DialogActionHandler,
    DialogActionOutcome,
    DialogFocusGuard,
    DialogFocusLocation,
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


def test_dialog_focus_guard_only_accepts_single_player_start() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
        focused_border_mean_max=180.0,
        minimum_contrast=20.0,
    )
    safe = np.full((100, 100, 3), 240, dtype=np.uint8)
    safe[70, 60:90] = 100
    unsafe = np.full((100, 100, 3), 240, dtype=np.uint8)
    unsafe[70, 25:55] = 100
    safe_dotted = np.full((100, 100, 3), 240, dtype=np.uint8)
    safe_dotted[73, 64:86:2] = 0
    safe_dotted[78, 64:86:2] = 0
    safe_dotted[73:79:2, 64] = 0
    safe_dotted[73:79:2, 85] = 0

    assert guard(safe)
    assert guard(safe_dotted)
    assert not guard(unsafe)
    assert guard.focus_location(safe) is DialogFocusLocation.START
    assert (
        guard.focus_location(unsafe)
        is DialogFocusLocation.TWO_PLAYER
    )


def test_dialog_waits_for_two_player_focus_to_recover_without_input() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
        focused_border_mean_max=180.0,
        minimum_contrast=20.0,
    )
    two_player = np.full((100, 100, 3), 240, dtype=np.uint8)
    two_player[70, 25:55] = 100
    start = np.full((100, 100, 3), 240, dtype=np.uint8)
    start[70, 60:90] = 100
    delayed = np.full((100, 100, 3), 240, dtype=np.uint8)
    playing = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = SequenceDetector(
        [
            GamePhase.DIALOG,
            GamePhase.DIALOG,
            GamePhase.DIALOG,
            GamePhase.DIALOG,
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
        frame_source(
            [
                two_player,
                two_player,
                delayed,
                delayed,
                start,
                start,
                playing,
                playing,
            ]
        ),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=2,
        focus_max_observation_frames=6,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        focus_guard=guard,
        focus_correction_key="right",
        focus_correction_duration_ms=80,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.outcome is DialogActionOutcome.PLAYING
    assert not result.focus_corrected
    assert result.focus_recovered_without_input
    assert controller.taps == [("enter", 200)]


def test_dialog_retries_key_up_cleanup_before_rejecting_two_player_focus() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
    )
    two_player = np.full((100, 100, 3), 240, dtype=np.uint8)
    two_player[70, 25:55] = 100
    start = np.full((100, 100, 3), 240, dtype=np.uint8)
    start[70, 60:90] = 100
    playing = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = SequenceDetector(
        [GamePhase.DIALOG] * 6
        + [GamePhase.PLAYING, GamePhase.PLAYING]
    )
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(
            [
                two_player,
                two_player,
                two_player,
                two_player,
                start,
                start,
                playing,
                playing,
            ]
        ),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=2,
        focus_max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        focus_guard=guard,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.outcome is DialogActionOutcome.PLAYING
    assert result.focus_recovered_without_input
    assert not result.focus_corrected
    assert controller.taps == [("enter", 200)]
    assert controller.release_count >= 4


def test_dialog_corrects_only_after_passive_focus_wait_expires() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
    )
    two_player = np.full((100, 100, 3), 240, dtype=np.uint8)
    two_player[70, 25:55] = 100
    start = np.full((100, 100, 3), 240, dtype=np.uint8)
    start[70, 60:90] = 100
    playing = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = SequenceDetector(
        [GamePhase.DIALOG] * 8
        + [GamePhase.PLAYING, GamePhase.PLAYING]
    )
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(
            [
                two_player,
                two_player,
                two_player,
                two_player,
                two_player,
                two_player,
                start,
                start,
                playing,
                playing,
            ]
        ),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=2,
        focus_max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        focus_guard=guard,
        focus_correction_key="right",
        focus_correction_duration_ms=80,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.focus_corrected
    assert not result.focus_recovered_without_input
    assert controller.taps == [("right", 80), ("enter", 200)]


def test_dialog_uses_longer_wait_after_single_focus_correction() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
    )
    two_player = np.full((100, 100, 3), 240, dtype=np.uint8)
    two_player[70, 25:55] = 100
    unknown = np.full((100, 100, 3), 240, dtype=np.uint8)
    start = np.full((100, 100, 3), 240, dtype=np.uint8)
    start[70, 60:90] = 100
    playing = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = SequenceDetector(
        [GamePhase.DIALOG] * 10
        + [GamePhase.PLAYING, GamePhase.PLAYING]
    )
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(
            [two_player] * 6
            + [unknown, unknown, start, start, playing, playing]
        ),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=2,
        focus_max_observation_frames=2,
        focus_correction_max_observation_frames=4,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        focus_guard=guard,
        focus_correction_key="tab",
        focus_correction_duration_ms=80,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.focus_corrected
    assert result.outcome is DialogActionOutcome.PLAYING
    assert controller.taps == [("tab", 80), ("enter", 200)]


def test_dialog_allows_bounded_multi_tab_correction() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
    )
    two_player = np.full((100, 100, 3), 240, dtype=np.uint8)
    two_player[70, 25:55] = 100
    unknown = np.full((100, 100, 3), 240, dtype=np.uint8)
    start = np.full((100, 100, 3), 240, dtype=np.uint8)
    start[70, 60:90] = 100
    playing = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = SequenceDetector(
        [GamePhase.DIALOG] * 16
        + [GamePhase.PLAYING, GamePhase.PLAYING]
    )
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source(
            [two_player] * 6
            + [unknown] * 8
            + [start] * 2
            + [playing] * 2
        ),
        key_duration_ms=200,
        required_consecutive=2,
        max_observation_frames=2,
        focus_max_observation_frames=2,
        focus_correction_max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        focus_guard=guard,
        focus_correction_key="tab",
        focus_correction_duration_ms=80,
        focus_correction_max_presses=3,
        sleep_fn=lambda _seconds: None,
    )

    result = handler.execute_once()

    assert result.focus_corrected
    assert result.outcome is DialogActionOutcome.PLAYING
    assert controller.taps == [
        ("tab", 80),
        ("tab", 80),
        ("tab", 80),
        ("enter", 200),
    ]


def test_dialog_unknown_focus_never_attempts_correction_or_enter() -> None:
    guard = DialogFocusGuard(
        reference_width=100,
        reference_height=100,
        start_button_rect=(60, 70, 30, 12),
        two_player_button_rect=(25, 70, 30, 12),
    )
    unknown = np.full((100, 100, 3), 240, dtype=np.uint8)
    detector = SequenceDetector([GamePhase.DIALOG, GamePhase.DIALOG])
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source([unknown, unknown]),
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        focus_guard=guard,
        focus_correction_key="right",
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(DialogActionError, match="焦點"):
        handler.execute_once()

    assert controller.taps == []


def test_dialog_does_not_press_enter_when_start_focus_is_unconfirmed() -> None:
    before = np.zeros((20, 30, 3), dtype=np.uint8)
    detector = SequenceDetector([GamePhase.DIALOG, GamePhase.DIALOG])
    controller = FakeController()
    handler = DialogActionHandler(
        detector,
        controller,
        "enter",
        frame_source([before, before]),
        required_consecutive=2,
        max_observation_frames=2,
        observation_delay_seconds=0,
        post_action_delay_seconds=0,
        confirm_guard=lambda _frame: False,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(DialogActionError, match="單人開始"):
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
