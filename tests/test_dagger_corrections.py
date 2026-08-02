from __future__ import annotations

from stair_agent.training.dagger_corrections import (
    classify_disagreement,
    terminal_aware_category,
)


def classify(**overrides):
    values = {
        "player": {"center_x": 317.0, "velocity_x": 0.0},
        "visible_platform_kinds": ["normal"],
        "width": 634.0,
        "player_width": 24.0,
        "teacher_action": 1,
        "learner_action": 2,
        "learner_confidence": 0.7,
    }
    values.update(overrides)
    return classify_disagreement(**values)


def test_spike_visible_and_terminal_risk_have_explicit_categories() -> None:
    assert classify(visible_platform_kinds=["normal", "spikes"]) == (
        "spike_visible_disagreement"
    )
    assert terminal_aware_category(
        "spike_visible_disagreement",
        terminal_reason="bottom",
        steps_to_terminal=19,
    ) == "bottom_terminal_risk"
    assert terminal_aware_category(
        "spike_visible_disagreement",
        terminal_reason="bottom",
        steps_to_terminal=20,
    ) == "spike_visible_disagreement"


def test_high_confidence_and_braking_disagreements_are_separated() -> None:
    assert classify(learner_confidence=0.9) == "high_confidence_disagreement"
    assert classify(
        teacher_action=0,
        learner_action=2,
        learner_confidence=0.9,
        player={"center_x": 317.0, "velocity_x": 100.0},
    ) == "brake_too_late"
