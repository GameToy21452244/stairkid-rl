from stair_agent.game_state import GamePhase
from stair_agent.session_controller import (
    SessionEvent,
    SessionState,
    SessionStateMachine,
)


def test_initial_dialog_is_not_counted_as_death() -> None:
    machine = SessionStateMachine()

    transition = machine.update(GamePhase.DIALOG)

    assert transition.previous is SessionState.WAITING_FOR_GAME
    assert transition.current is SessionState.DIALOG
    assert transition.event is SessionEvent.DIALOG_DETECTED


def test_dialog_to_playing_starts_round() -> None:
    machine = SessionStateMachine()
    machine.update(GamePhase.DIALOG)
    machine.mark_starting()

    transition = machine.update(GamePhase.PLAYING)

    assert transition.previous is SessionState.STARTING
    assert transition.current is SessionState.PLAYING
    assert transition.event is SessionEvent.ROUND_STARTED
    assert machine.round_count == 1


def test_playing_to_dialog_ends_round_once() -> None:
    machine = SessionStateMachine()
    machine.update(GamePhase.DIALOG)
    machine.mark_starting()
    machine.update(GamePhase.PLAYING)

    first = machine.update(GamePhase.DIALOG)
    repeated = machine.update(GamePhase.DIALOG)

    assert first.current is SessionState.ROUND_ENDED
    assert first.event is SessionEvent.ROUND_ENDED
    assert repeated.current is SessionState.ROUND_ENDED
    assert repeated.event is SessionEvent.NONE
    assert machine.completed_rounds == 1


def test_name_entry_is_a_blocking_dialog_phase() -> None:
    machine = SessionStateMachine()
    machine.update(GamePhase.PLAYING)

    transition = machine.update(GamePhase.NAME_ENTRY)

    assert transition.current is SessionState.ROUND_ENDED
    assert transition.event is SessionEvent.ROUND_ENDED


def test_unknown_reports_lost_state_without_counting_round() -> None:
    machine = SessionStateMachine()
    machine.update(GamePhase.PLAYING)

    transition = machine.update(GamePhase.UNKNOWN)

    assert transition.current is SessionState.UNKNOWN
    assert transition.event is SessionEvent.STATE_LOST
    assert machine.completed_rounds == 0


def test_emergency_stop_is_sticky() -> None:
    machine = SessionStateMachine()
    stopped = machine.emergency_stop()
    later = machine.update(GamePhase.PLAYING)

    assert stopped.current is SessionState.EMERGENCY_STOPPED
    assert stopped.event is SessionEvent.EMERGENCY_STOPPED
    assert later.current is SessionState.EMERGENCY_STOPPED
    assert later.event is SessionEvent.NONE
