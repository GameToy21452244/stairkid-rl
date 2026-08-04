"""Frozen v0.3 Oracle robustness Gate helpers."""

from __future__ import annotations

from typing import Any

from ..policies.simulator_teachers import OracleFull
from .simulator_v03_edge_gate import (
    ActionChooser,
    EdgeEvaluation,
    oracle_checks,
)


DEVELOPMENT_SEEDS = tuple(range(16000, 16100))
HOLDOUT_SEEDS = tuple(range(17000, 17100))
RETIRED_FAILURE_SEEDS = (
    14005,
    14013,
    14025,
    14057,
    14060,
    14061,
    14065,
)
EXPECTED_DIAGNOSTIC_COUNTS = {
    "current_v6": 0,
    "receding_current_trigger": 4,
    "always_receding": 0,
    "extended_always_receding": 0,
}
ORACLE_V7_POLICY_VERSION = "oracle-full-v7-receding-route-planner"


def create_receding_route_planner_oracle() -> OracleFull:
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="receding",
    )
    if oracle.policy_version != ORACLE_V7_POLICY_VERSION:
        raise RuntimeError("Oracle v7 policy version 不一致。")
    return oracle


def receding_route_planner_oracle_factory() -> ActionChooser:
    oracle = create_receding_route_planner_oracle()
    return lambda env: oracle.choose(env.simulator).action


def taxonomy_source_checks(payload: dict[str, Any]) -> dict[str, bool]:
    results = payload.get("failure_results") or []
    failure_seeds = tuple(
        int(item["seed"])
        for item in results
        if isinstance(item, dict) and "seed" in item
    )
    return {
        "status_is_evidence_open_loop_primary": (
            payload.get("status") == "EVIDENCE_OPEN_LOOP_PRIMARY"
        ),
        "is_not_formal_gate": payload.get("formal_gate") is False,
        "uses_retired_diagnostic_seeds_only": (
            payload.get("retired_diagnostic_seeds_only") is True
        ),
        "diagnostic_counts_match_frozen_result": (
            payload.get("mode_reach_floor_10_counts_out_of_7")
            == EXPECTED_DIAGNOSTIC_COUNTS
        ),
        "retired_failure_seeds_match_exactly": (
            failure_seeds == RETIRED_FAILURE_SEEDS
        ),
        "all_v6_failures_reproduced": (
            payload.get("all_current_v6_failures_reproduced") is True
        ),
        "all_planner_calls_restored_state": (
            payload.get("all_planner_calls_restored_state") is True
        ),
        "all_searches_within_fixed_bounds": (
            payload.get("all_searches_within_fixed_bounds") is True
        ),
    }


def development_oracle_checks(
    reference_v6: EdgeEvaluation,
    candidate_v7: EdgeEvaluation,
) -> dict[str, bool]:
    return {
        **oracle_checks(candidate_v7),
        "reach_floor_10_not_below_v6_reference": (
            candidate_v7.reach_floor_10_rate
            >= reference_v6.reach_floor_10_rate
        ),
    }


def _all(checks: dict[str, bool] | None) -> bool:
    return bool(checks) and all(checks.values())


def decide_gate_status(
    *,
    source_checks: dict[str, bool],
    development_reachability_passed: bool | None,
    development_checks: dict[str, bool] | None,
    holdout_reachability_passed: bool | None,
    holdout_oracle_checks: dict[str, bool] | None,
    holdout_candidate_checks: dict[str, bool] | None,
) -> str:
    if not _all(source_checks):
        return "FAIL_STOP_SOURCE_INTEGRITY"
    if development_reachability_passed is not True:
        return "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
    if not _all(development_checks):
        return "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"
    if holdout_reachability_passed is not True:
        return "FAIL_STOP_ORACLE_ROBUSTNESS_HOLDOUT"
    if not _all(holdout_oracle_checks):
        return "FAIL_STOP_ORACLE_ROBUSTNESS_HOLDOUT"
    if not _all(holdout_candidate_checks):
        return "FAIL_STOP_ROUTE_INTENT_HOLDOUT"
    return "PASS_ORACLE_ROBUSTNESS_AND_ROUTE_INTENT"


__all__ = [
    "DEVELOPMENT_SEEDS",
    "EXPECTED_DIAGNOSTIC_COUNTS",
    "HOLDOUT_SEEDS",
    "ORACLE_V7_POLICY_VERSION",
    "RETIRED_FAILURE_SEEDS",
    "create_receding_route_planner_oracle",
    "decide_gate_status",
    "development_oracle_checks",
    "receding_route_planner_oracle_factory",
    "taxonomy_source_checks",
]

