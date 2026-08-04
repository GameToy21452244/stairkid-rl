from __future__ import annotations

import pytest

from stair_agent.training.simulator_oracle_failure_taxonomy import (
    DIAGNOSTIC_MODES,
    RETIRED_FAILURE_EXPECTATIONS,
    DiagnosticEpisode,
    counterfactual_attribution,
    current_failure_phenotype,
    run_diagnostic_episode,
)


def _episode(mode: str, floor: int) -> DiagnosticEpisode:
    return DiagnosticEpisode(
        mode=mode,
        seed=1,
        steps=1,
        deepest_floor=floor,
        terminal_reason="target_reached" if floor >= 10 else "top",
        planning_count=0,
        total_expanded_nodes=0,
        max_expanded_nodes=0,
        planner_state_restored=True,
        plan_traces=(),
    )


@pytest.mark.parametrize(
    ("rescued_mode", "expected"),
    [
        ("receding_current_trigger", "open_loop_execution"),
        ("always_receding", "late_trigger"),
        ("extended_always_receding", "bounded_search_capacity"),
        (None, "unresolved_bounded_search"),
    ],
)
def test_counterfactual_attribution_priority(
    rescued_mode: str | None,
    expected: str,
) -> None:
    episodes = [
        _episode(mode, 10 if mode == rescued_mode else 3)
        for mode in DIAGNOSTIC_MODES
    ]
    assert counterfactual_attribution(episodes) == expected


def test_current_v6_retired_failures_reproduce_exactly() -> None:
    for seed, expected in RETIRED_FAILURE_EXPECTATIONS.items():
        result = run_diagnostic_episode(seed, "current_v6")
        assert (result.deepest_floor, result.terminal_reason) == expected
        assert result.planner_state_restored


def test_pre_trigger_failure_is_classified() -> None:
    result = run_diagnostic_episode(14057, "current_v6")
    assert current_failure_phenotype(result) == "pre_trigger_bottom"


def test_future_seed_partitions_do_not_reuse_existing_gate_seeds() -> None:
    used = set(range(13000, 14100))
    development = set(range(16000, 16100))
    holdout = set(range(17000, 17100))
    assert not used & development
    assert not used & holdout
    assert not development & holdout

