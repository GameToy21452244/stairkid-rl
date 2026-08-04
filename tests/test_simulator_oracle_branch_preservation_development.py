from __future__ import annotations

from pathlib import Path

import pytest

from stair_agent.training.simulator_oracle_branch_preservation_development import (
    aggregate_branch_metrics,
    episode_reproducible,
    paired_branch_diagnostics,
    run_branch_episode,
    validate_development_execution_seeds,
)
from stair_agent.training.simulator_oracle_branch_preservation_gate import (
    PRIMARY_DEVELOPMENT_SEEDS,
)


def test_development_seed_validation_never_accepts_old_or_holdout_seeds() -> None:
    assert validate_development_execution_seeds(
        PRIMARY_DEVELOPMENT_SEEDS
    ) == PRIMARY_DEVELOPMENT_SEEDS
    with pytest.raises(ValueError):
        validate_development_execution_seeds(tuple(range(16000, 16100)))
    with pytest.raises(ValueError):
        validate_development_execution_seeds(tuple(range(17000, 17100)))
    with pytest.raises(ValueError):
        validate_development_execution_seeds(tuple(range(19000, 19100)))


def test_diagnostic_nonterminal_path_matches_v6_without_new_seeds() -> None:
    reference = run_branch_episode(16000, "cached", diagnostic=True)
    candidate = run_branch_episode(
        16000,
        "branch_preserved",
        diagnostic=True,
    )
    paired = paired_branch_diagnostics(reference, candidate)
    assert paired["non_terminal_reference_path"]
    assert paired["action_sequence_identical"]
    assert candidate.branch_preserved_search_count == 0


def test_diagnostic_top_failure_records_branch_telemetry() -> None:
    reference = run_branch_episode(16002, "cached", diagnostic=True)
    candidate = run_branch_episode(
        16002,
        "branch_preserved",
        diagnostic=True,
    )
    paired = paired_branch_diagnostics(reference, candidate)
    assert reference.terminal_reason == "top"
    assert candidate.deepest_floor >= 10
    assert paired["v6_top_failure_repaired"]
    assert candidate.branch_preserved_search_count >= 1
    assert candidate.selected_lane_counts["RIGHT"] >= 1
    assert candidate.all_plans_within_bounds
    assert not candidate.safety_violations


def test_aggregate_contains_frozen_tail_switch_and_compute_metrics() -> None:
    episodes = (
        run_branch_episode(16000, "cached", diagnostic=True),
        run_branch_episode(16002, "cached", diagnostic=True),
    )
    metrics = aggregate_branch_metrics(episodes)
    for key in (
        "reach_floor_3_rate",
        "reach_floor_5_rate",
        "reach_floor_10_rate",
        "mean",
        "median",
        "q25",
        "cvar25",
        "action_switches_per_100_steps",
        "direct_left_right_reversals",
        "release_bridged_reversals",
        "branch_preserved_search_count",
        "selected_lane_distribution",
        "branch_compute",
        "safety_violations",
    ):
        assert key in metrics


def test_duplicate_diagnostic_episode_is_reproducible() -> None:
    first = run_branch_episode(
        16002,
        "branch_preserved",
        diagnostic=True,
    )
    second = run_branch_episode(
        16002,
        "branch_preserved",
        diagnostic=True,
    )
    assert episode_reproducible(first, second)


def test_development_runner_cannot_import_or_execute_holdout() -> None:
    source = Path(
        "scripts/run_simulator_oracle_branch_preservation_development.py"
    ).read_text(encoding="utf-8")
    assert "HOLDOUT_SEEDS" not in source
    assert "19000" not in source
    assert "run_simulator_oracle_branch_preservation_holdout.py" in source
    assert "INCOMPLETE" in source
    assert "holdout_used" in source
