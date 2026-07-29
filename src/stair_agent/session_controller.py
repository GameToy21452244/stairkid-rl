from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .game_state import GamePhase


class SessionState(Enum):
    WAITING_FOR_GAME = "waiting_for_game"
    DIALOG = "dialog"
    STARTING = "starting"
    PLAYING = "playing"
    ROUND_ENDED = "round_ended"
    UNKNOWN = "unknown"
    EMERGENCY_STOPPED = "emergency_stopped"


class SessionEvent(Enum):
    NONE = "none"
    DIALOG_DETECTED = "dialog_detected"
    ROUND_STARTED = "round_started"
    ROUND_ENDED = "round_ended"
    STATE_LOST = "state_lost"
    EMERGENCY_STOPPED = "emergency_stopped"


class SessionStateError(RuntimeError):
    """回合狀態轉移不合法。"""


@dataclass(frozen=True)
class SessionTransition:
    previous: SessionState
    current: SessionState
    event: SessionEvent
    observed_phase: GamePhase


_BLOCKING_PHASES = {
    GamePhase.DIALOG,
    GamePhase.NAME_ENTRY,
    GamePhase.MENU,
    GamePhase.GAME_OVER,
}


class SessionStateMachine:
    """將單幀遊戲 phase 轉換成具時間語意的回合事件。"""

    def __init__(self) -> None:
        self.state = SessionState.WAITING_FOR_GAME
        self.round_count = 0
        self.completed_rounds = 0
        self.last_phase = GamePhase.UNKNOWN

    def _transition(
        self,
        current: SessionState,
        event: SessionEvent,
        phase: GamePhase,
    ) -> SessionTransition:
        previous = self.state
        self.state = current
        self.last_phase = phase
        return SessionTransition(previous, current, event, phase)

    def mark_starting(self) -> SessionTransition:
        if self.state not in {
            SessionState.DIALOG,
            SessionState.ROUND_ENDED,
            SessionState.WAITING_FOR_GAME,
        }:
            raise SessionStateError(
                f"只有等待或對話框狀態可標記 STARTING，目前為 {self.state.value}。"
            )
        return self._transition(
            SessionState.STARTING,
            SessionEvent.NONE,
            self.last_phase,
        )

    def emergency_stop(self) -> SessionTransition:
        return self._transition(
            SessionState.EMERGENCY_STOPPED,
            SessionEvent.EMERGENCY_STOPPED,
            self.last_phase,
        )

    def update(self, phase: GamePhase) -> SessionTransition:
        if self.state is SessionState.EMERGENCY_STOPPED:
            return self._transition(
                SessionState.EMERGENCY_STOPPED,
                SessionEvent.NONE,
                phase,
            )

        if phase is GamePhase.UNKNOWN:
            event = (
                SessionEvent.NONE
                if self.state is SessionState.UNKNOWN
                else SessionEvent.STATE_LOST
            )
            return self._transition(SessionState.UNKNOWN, event, phase)

        if phase is GamePhase.PLAYING:
            event = (
                SessionEvent.NONE
                if self.state is SessionState.PLAYING
                else SessionEvent.ROUND_STARTED
            )
            if event is SessionEvent.ROUND_STARTED:
                self.round_count += 1
            return self._transition(SessionState.PLAYING, event, phase)

        if phase in _BLOCKING_PHASES:
            if self.state is SessionState.PLAYING:
                self.completed_rounds += 1
                return self._transition(
                    SessionState.ROUND_ENDED,
                    SessionEvent.ROUND_ENDED,
                    phase,
                )
            if self.state is SessionState.ROUND_ENDED:
                return self._transition(
                    SessionState.ROUND_ENDED,
                    SessionEvent.NONE,
                    phase,
                )
            event = (
                SessionEvent.NONE
                if self.state is SessionState.DIALOG
                else SessionEvent.DIALOG_DETECTED
            )
            return self._transition(SessionState.DIALOG, event, phase)

        return self._transition(
            SessionState.UNKNOWN,
            SessionEvent.STATE_LOST,
            phase,
        )
