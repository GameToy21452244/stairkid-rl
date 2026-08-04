from __future__ import annotations

from stair_agent.training.simulator_oracle_receding_failure_audit import (
    BOTH_FAILURE_SEEDS,
    CONTROL_SEEDS,
    REGRESSION_SEEDS,
    RESCUE_SEEDS,
    classify_first_divergence,
    horizontal_switches,
    select_audit_seeds,
)


def _episode(seed: int, floor: int) -> dict[str, object]:
    return {"seed": seed, "deepest_floor": floor}


def test_frozen_audit_seed_groups_are_disjoint() -> None:
    groups = [
        set(REGRESSION_SEEDS),
        set(RESCUE_SEEDS),
        set(BOTH_FAILURE_SEEDS),
        set(CONTROL_SEEDS),
    ]
    assert [len(group) for group in groups] == [21, 1, 3, 10]
    assert all(
        not groups[left] & groups[right]
        for left in range(len(groups))
        for right in range(left + 1, len(groups))
    )


def test_artifact_selection_matches_frozen_groups() -> None:
    reference = []
    candidate = []
    for seed in range(16000, 16100):
        if seed in REGRESSION_SEEDS:
            old_floor, new_floor = 10, 4
        elif seed in RESCUE_SEEDS:
            old_floor, new_floor = 4, 10
        elif seed in BOTH_FAILURE_SEEDS:
            old_floor, new_floor = 4, 4
        else:
            old_floor, new_floor = 10, 10
        reference.append(_episode(seed, old_floor))
        candidate.append(_episode(seed, new_floor))
    selected = select_audit_seeds(reference, candidate)
    assert selected == {
        "regression": REGRESSION_SEEDS,
        "rescue": RESCUE_SEEDS,
        "both_failure": BOTH_FAILURE_SEEDS,
        "control": CONTROL_SEEDS,
    }


def test_horizontal_switches_ignores_release_bridge() -> None:
    assert horizontal_switches(("LEFT", "RIGHT", "LEFT")) == 2
    assert horizontal_switches(("LEFT", "RELEASE_ALL", "RIGHT")) == 0


def test_first_divergence_classification() -> None:
    assert classify_first_divergence(
        v6_action="LEFT",
        v7_action="RIGHT",
        v6_cached_before=3,
        v7_planned_now=True,
    ) == "cached_vs_replan_opposite"
    assert classify_first_divergence(
        v6_action="RELEASE_ALL",
        v7_action="RIGHT",
        v6_cached_before=2,
        v7_planned_now=True,
    ) == "cached_vs_replan_release"
    assert classify_first_divergence(
        v6_action="LEFT",
        v7_action="RIGHT",
        v6_cached_before=0,
        v7_planned_now=True,
    ) == "fallback_or_trigger_divergence"

