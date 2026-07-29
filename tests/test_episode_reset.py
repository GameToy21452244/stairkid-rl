import numpy as np
import pytest

from stair_agent.dialog_handler import (
    DialogActionOutcome,
    DialogActionResult,
    StableObservation,
)
from stair_agent.episode_reset import EpisodeResetError, SingleEnterEpisodeResetter
from stair_agent.game_state import GamePhase
from stair_agent.observation import GameObservation


def stable(phase):
    return StableObservation(
        phase,
        0.99,
        np.zeros((10, 10, 3), dtype=np.uint8),
        3,
    )


def observation(phase="playing"):
    return GameObservation(
        timestamp=1.0,
        phase=phase,
        player=None,
        health={"segments": 12, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=[],
    )


class FakeHandler:
    def __init__(self, before, outcome=None):
        self.before = before
        self.outcome = outcome
        self.execute_calls = []

    def observe_stable(self):
        return self.before

    def execute_once(self, before=None):
        self.execute_calls.append(before)
        after_phase = (
            GamePhase.PLAYING
            if self.outcome is DialogActionOutcome.PLAYING
            else GamePhase.DIALOG
        )
        return DialogActionResult(
            before,
            stable(after_phase),
            self.outcome,
            0.1,
        )


class FakeController:
    def __init__(self):
        self.release_count = 0

    def release_all(self):
        self.release_count += 1


def make_resetter(handler, observed):
    controller = FakeController()
    reset_calls = []
    resetter = SingleEnterEpisodeResetter(
        handler=handler,
        controller=controller,
        observe=lambda: observed,
        reset_pipeline=lambda: reset_calls.append(True),
    )
    return resetter, controller, reset_calls


def test_reset_while_already_playing_never_sends_enter() -> None:
    handler = FakeHandler(stable(GamePhase.PLAYING))
    resetter, controller, reset_calls = make_resetter(
        handler,
        observation(),
    )

    result = resetter.reset()

    assert result.phase == "playing"
    assert handler.execute_calls == []
    assert not resetter.last_enter_sent
    assert reset_calls == [True]
    assert controller.release_count >= 2


def test_dialog_reset_sends_at_most_one_enter_and_requires_playing() -> None:
    handler = FakeHandler(
        stable(GamePhase.DIALOG),
        DialogActionOutcome.PLAYING,
    )
    resetter, controller, reset_calls = make_resetter(
        handler,
        observation(),
    )

    result = resetter.reset()

    assert result.phase == "playing"
    assert handler.execute_calls == [handler.before]
    assert resetter.last_enter_sent
    assert reset_calls == [True]
    assert controller.release_count >= 2


def test_changed_dialog_stops_without_second_enter() -> None:
    handler = FakeHandler(
        stable(GamePhase.DIALOG),
        DialogActionOutcome.DIALOG_CHANGED,
    )
    resetter, controller, reset_calls = make_resetter(
        handler,
        observation(),
    )

    with pytest.raises(EpisodeResetError, match="一次 Enter"):
        resetter.reset()

    assert len(handler.execute_calls) == 1
    assert resetter.last_enter_sent
    assert reset_calls == []
    assert controller.release_count >= 1


def test_unknown_phase_never_sends_enter() -> None:
    handler = FakeHandler(stable(GamePhase.UNKNOWN))
    resetter, controller, _reset_calls = make_resetter(
        handler,
        observation(),
    )

    with pytest.raises(EpisodeResetError, match="unknown"):
        resetter.reset()

    assert handler.execute_calls == []
    assert not resetter.last_enter_sent
    assert controller.release_count >= 1


def test_structured_observation_must_still_be_playing() -> None:
    handler = FakeHandler(stable(GamePhase.PLAYING))
    resetter, controller, _reset_calls = make_resetter(
        handler,
        observation("dialog"),
    )

    with pytest.raises(EpisodeResetError, match="重新擷取"):
        resetter.reset()

    assert handler.execute_calls == []
    assert controller.release_count >= 1
