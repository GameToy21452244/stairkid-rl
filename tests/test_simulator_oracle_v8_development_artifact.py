from __future__ import annotations

from pathlib import Path

import pytest

from stair_agent.training.simulator_oracle_v8_development_artifact import (
    DEVELOPMENT_SEEDS,
    action_sequence_metrics,
    floor_distribution_metrics,
    paired_episode_diagnostics,
    paired_outcome_metrics,
    run_development_episode,
    switch_inflation_checks,
    validate_development_seeds,
)


def test_development_partition_is_exact_and_rejects_holdout() -> None:
    assert DEVELOPMENT_SEEDS == tuple(range(16000, 16100))
    assert validate_development_seeds(DEVELOPMENT_SEEDS) == DEVELOPMENT_SEEDS
    with pytest.raises(ValueError):
        validate_development_seeds(tuple(range(16000, 16099)))
    with pytest.raises(ValueError):
        validate_development_seeds(tuple(range(17000, 17100)))


def test_distribution_and_action_diagnostics_are_deterministic() -> None:
    distribution = floor_distribution_metrics((0, 1, 2, 3, 10, 10, 10, 10))
    assert distribution == {
        "mean": 5.75,
        "median": 6.5,
        "q25": 1.75,
        "cvar25": 0.5,
    }
    metrics = action_sequence_metrics((
        "LEFT",
        "RIGHT",
        "RELEASE_ALL",
        "RELEASE_ALL",
        "LEFT",
        "LEFT",
        "RELEASE_ALL",
        "RIGHT",
    ))
    assert metrics["action_switch_count"] == 5
    assert metrics["direct_left_right_reversals"] == 1
    assert metrics["release_bridged_reversals"] == 2
    assert metrics["action_counts"] == {
        "RELEASE_ALL": 3,
        "LEFT": 3,
        "RIGHT": 2,
    }


def test_paired_outcomes_and_switch_limit_are_frozen_before_run() -> None:
    reference = (
        {"seed": 1, "deepest_floor": 10},
        {"seed": 2, "deepest_floor": 5},
        {"seed": 3, "deepest_floor": 6},
        {"seed": 4, "deepest_floor": 10},
    )
    candidate = (
        {"seed": 1, "deepest_floor": 10},
        {"seed": 2, "deepest_floor": 10},
        {"seed": 3, "deepest_floor": 6},
        {"seed": 4, "deepest_floor": 4},
    )
    assert paired_outcome_metrics(reference, candidate) == {
        "both_success": 1,
        "v6_only_success": 1,
        "v8_only_success": 1,
        "both_failure": 1,
    }
    assert all(switch_inflation_checks(
        v6_switches=100,
        v6_steps=1000,
        v8_switches=104,
        v8_steps=1000,
        non_terminal_paths_identical=True,
    ).values())
    assert not switch_inflation_checks(
        v6_switches=100,
        v6_steps=1000,
        v8_switches=106,
        v8_steps=1000,
        non_terminal_paths_identical=True,
    )["action_switch_rate_inflation_at_most_5_percent"]


def test_non_terminal_development_trace_keeps_v6_path() -> None:
    reference = run_development_episode(16000, "cached")
    candidate = run_development_episode(16000, "terminal_guarded")
    paired = paired_episode_diagnostics(reference, candidate)
    assert reference.terminal_plan_count == 0
    assert paired["action_sequence_identical"]
    assert paired["first_divergence"] is None
    assert paired["outcome"] == "both_success"


def test_development_runner_has_no_holdout_execution_import() -> None:
    source = Path(
        "scripts/run_simulator_oracle_v8_development.py"
    ).read_text(encoding="utf-8")
    assert "HOLDOUT_SEEDS" not in source
    assert "run_simulator_oracle_v8_gate.py" in source
    assert '"used": False' in source
    assert "item.seed: asdict(item)" in source
    assert "item.to_dict()" not in source
    assert '"attempt_history": attempt_history' in source
