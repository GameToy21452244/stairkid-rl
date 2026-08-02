from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def classify_disagreement(
    *,
    player: dict[str, Any] | None,
    visible_platform_kinds: Iterable[str],
    width: float,
    player_width: float,
    teacher_action: int,
    learner_action: int,
    learner_confidence: float,
) -> str:
    player = player or {}
    x = float(player.get("center_x", width / 2))
    vx = float(player.get("velocity_x", 0.0))
    margin = player_width * 1.5
    if "spikes" in visible_platform_kinds:
        return "spike_visible_disagreement"
    if x <= margin or x >= width - margin:
        return "wall_collision"
    if teacher_action == 0 and learner_action in {1, 2} and abs(vx) > 60:
        return "brake_too_late"
    if learner_confidence >= 0.80:
        return "high_confidence_disagreement"
    if teacher_action in {1, 2} and learner_action in {1, 2}:
        return "wrong_target"
    return "missed_platform_risk"


def terminal_aware_category(
    category: str,
    *,
    terminal_reason: str,
    steps_to_terminal: int,
) -> str:
    if steps_to_terminal < 20 and terminal_reason in {"top", "bottom"}:
        return f"{terminal_reason}_terminal_risk"
    return category


__all__ = ["classify_disagreement", "terminal_aware_category"]
