from __future__ import annotations

import pytest

from stair_agent.training.simulator_oracle_branch_preservation_gate import (
    CONDITIONAL_DEVELOPMENT_EXTENSION,
    HOLDOUT_SEEDS,
    PRIMARY_DEVELOPMENT_SEEDS,
    branch_preservation_development_checks,
    branch_preservation_holdout_checks,
    holdout_allowed,
    incomplete_stage_payload,
    select_development_seeds,
    validate_partition,
)


def test_seed_ledger_enforces_new_partitions_and_rejects_17000() -> None:
    assert PRIMARY_DEVELOPMENT_SEEDS == tuple(range(18000, 18100))
    assert CONDITIONAL_DEVELOPMENT_EXTENSION == tuple(range(18100, 18200))
    assert HOLDOUT_SEEDS == tuple(range(19000, 19100))
    assert validate_partition("development", PRIMARY_DEVELOPMENT_SEEDS) == (
        PRIMARY_DEVELOPMENT_SEEDS
    )
    assert validate_partition("holdout", HOLDOUT_SEEDS) == HOLDOUT_SEEDS
    with pytest.raises(ValueError):
        validate_partition("holdout", tuple(range(17000, 17100)))
    with pytest.raises(ValueError):
        validate_partition("development", tuple(range(16000, 16100)))


def test_zero_top_rule_is_frozen_before_development() -> None:
    assert select_development_seeds(v6_primary_top_failures=2) == (
        PRIMARY_DEVELOPMENT_SEEDS
    )
    assert select_development_seeds(v6_primary_top_failures=0) == (
        PRIMARY_DEVELOPMENT_SEEDS + CONDITIONAL_DEVELOPMENT_EXTENSION
    )


def _metrics(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "reach_floor_10_rate": 0.96,
        "q25": 10.0,
        "cvar25": 9.4,
        "bottom_deaths": 2,
        "health_deaths": 0,
        "safety_violations": 0,
        "collapsed": False,
        "steps": 1000,
        "action_switch_count": 100,
    }
    values.update(updates)
    return values


def test_development_gate_requires_top_repair_and_zero_regression() -> None:
    checks = branch_preservation_development_checks(
        reference=_metrics(),
        candidate=_metrics(),
        v6_success_regressions=0,
        v6_top_failures=2,
        v6_top_failures_repaired=1,
        non_terminal_paths_identical=True,
        reproducible=True,
        planner_bounds_passed=True,
    )
    assert all(checks.values())
    assert not branch_preservation_development_checks(
        reference=_metrics(),
        candidate=_metrics(),
        v6_success_regressions=0,
        v6_top_failures=2,
        v6_top_failures_repaired=0,
        non_terminal_paths_identical=True,
        reproducible=True,
        planner_bounds_passed=True,
    )["v6_top_failures_repaired_at_least_one"]
    assert not branch_preservation_development_checks(
        reference=_metrics(),
        candidate=_metrics(),
        v6_success_regressions=1,
        v6_top_failures=2,
        v6_top_failures_repaired=1,
        non_terminal_paths_identical=True,
        reproducible=True,
        planner_bounds_passed=True,
    )["v6_success_regressions_zero"]


def test_development_fail_hard_blocks_holdout() -> None:
    assert holdout_allowed({"a": True, "b": True})
    assert not holdout_allowed({"a": True, "b": False})
    assert not holdout_allowed(None)


def test_holdout_gate_includes_lower_tail_and_switch_limit() -> None:
    checks = branch_preservation_holdout_checks(
        reference=_metrics(),
        candidate=_metrics(),
        reproducible=True,
        planner_bounds_passed=True,
    )
    assert all(checks.values())
    failed = branch_preservation_holdout_checks(
        reference=_metrics(),
        candidate=_metrics(cvar25=9.0, action_switch_count=106),
        reproducible=True,
        planner_bounds_passed=True,
    )
    assert not failed["cvar25_not_below_v6"]
    assert not failed["action_switch_rate_inflation_at_most_5_percent"]


def test_interrupted_stage_is_incomplete_and_never_uses_holdout() -> None:
    artifact = incomplete_stage_payload(
        stage="development",
        reason="KeyboardInterrupt",
    )
    assert artifact["status"] == "INCOMPLETE"
    assert artifact["passed"] is False
    assert artifact["holdout"]["used"] is False
    assert artifact["stop_reason"] == "KeyboardInterrupt"
