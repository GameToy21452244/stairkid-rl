"""Frozen Oracle v8 terminal-risk Gate helpers."""

from __future__ import annotations

from typing import Any

from ..policies.simulator_teachers import OracleFull
from .simulator_v03_edge_gate import (
    ActionChooser,
    EdgeEpisode,
    EdgeEvaluation,
    oracle_checks,
)


ORACLE_V8_POLICY_VERSION = "oracle-full-v8-terminal-risk-guard"


def edge_evaluation_from_dict(payload: dict[str, Any]) -> EdgeEvaluation:
    episodes = tuple(
        EdgeEpisode(
            seed=int(item["seed"]),
            steps=int(item["steps"]),
            deepest_floor=int(item["deepest_floor"]),
            terminal_reason=item.get("terminal_reason"),
            action_counts={
                str(key): int(value)
                for key, value in item["action_counts"].items()
            },
            support_departures=int(item["support_departures"]),
            floor_descents=int(item["floor_descents"]),
            minimum_departure_clearance=item.get(
                "minimum_departure_clearance"
            ),
            invariant_violations=tuple(item["invariant_violations"]),
        )
        for item in payload["episode_results"]
    )
    return EdgeEvaluation(
        candidate=str(payload["candidate"]),
        episodes=int(payload["episodes"]),
        mean_deepest_floor=float(payload["mean_deepest_floor"]),
        reach_floor_3_rate=float(payload["reach_floor_3_rate"]),
        reach_floor_10_rate=float(payload["reach_floor_10_rate"]),
        max_action_share=float(payload["max_action_share"]),
        collapsed=bool(payload["collapsed"]),
        action_counts={
            str(key): int(value)
            for key, value in payload["action_counts"].items()
        },
        support_departures=int(payload["support_departures"]),
        floor_descents=int(payload["floor_descents"]),
        minimum_departure_clearance=payload.get(
            "minimum_departure_clearance"
        ),
        invariant_violation_count=int(payload["invariant_violation_count"]),
        episodes_with_violations=int(payload["episodes_with_violations"]),
        terminal_reasons={
            str(key): int(value)
            for key, value in payload["terminal_reasons"].items()
        },
        episode_results=episodes,
    )


def create_terminal_guard_oracle() -> OracleFull:
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    if oracle.policy_version != ORACLE_V8_POLICY_VERSION:
        raise RuntimeError("Oracle v8 policy version不一致。")
    return oracle


def terminal_guard_oracle_factory() -> ActionChooser:
    oracle = create_terminal_guard_oracle()
    return lambda env: oracle.choose(env.simulator).action


def terminal_audit_source_checks(payload: dict[str, Any]) -> dict[str, bool]:
    summaries = payload.get("development_group_summaries") or {}
    success = summaries.get("success") or {}
    top = summaries.get("top_failure") or {}
    bottom = summaries.get("bottom_failure") or {}
    evidence = payload.get("evidence_checks") or {}
    return {
        "status_is_terminal_risk_isolation": (
            payload.get("status") == "EVIDENCE_TERMINAL_RISK_ISOLATION"
        ),
        "holdout_was_unused": payload.get("holdout_used") is False,
        "success_group_is_exact_96_with_zero_exposure": (
            success.get("episodes") == 96
            and success.get("terminal_plan_exposed") == 0
        ),
        "top_group_is_exact_2_with_full_exposure": (
            top.get("episodes") == 2
            and top.get("terminal_plan_exposed") == 2
        ),
        "bottom_group_is_exact_2_with_zero_exposure": (
            bottom.get("episodes") == 2
            and bottom.get("terminal_plan_exposed") == 0
        ),
        "retired_search_failures_are_exact_3_with_full_exposure": (
            payload.get("retired_search_failure_count") == 3
            and payload.get(
                "retired_search_failure_terminal_plan_exposed"
            ) == 3
        ),
        "all_terminal_audit_evidence_checks_pass": (
            bool(evidence) and all(bool(value) for value in evidence.values())
        ),
    }


def paired_development_metrics(
    reference_v6: EdgeEvaluation,
    candidate_v8: EdgeEvaluation,
) -> dict[str, int]:
    old = {item.seed: item for item in reference_v6.episode_results}
    new = {item.seed: item for item in candidate_v8.episode_results}
    if set(old) != set(new):
        raise ValueError("v6／v8 development seeds不一致。")
    return {
        "v6_success_to_v8_failure": sum(
            old[seed].deepest_floor >= 10
            and new[seed].deepest_floor < 10
            for seed in old
        ),
        "v6_failure_to_v8_success": sum(
            old[seed].deepest_floor < 10
            and new[seed].deepest_floor >= 10
            for seed in old
        ),
        "v6_top_failure_repaired": sum(
            old[seed].terminal_reason == "top"
            and new[seed].deepest_floor >= 10
            for seed in old
        ),
        "v6_bottom_failure_repaired": sum(
            old[seed].terminal_reason == "bottom"
            and new[seed].deepest_floor >= 10
            for seed in old
        ),
    }


def v8_development_checks(
    reference_v6: EdgeEvaluation,
    candidate_v8: EdgeEvaluation,
) -> dict[str, bool]:
    metrics = paired_development_metrics(reference_v6, candidate_v8)
    return {
        **oracle_checks(candidate_v8),
        "reach_floor_10_not_below_v6_reference": (
            candidate_v8.reach_floor_10_rate
            >= reference_v6.reach_floor_10_rate
        ),
        "v6_success_regressions_zero": (
            metrics["v6_success_to_v8_failure"] == 0
        ),
        "v6_top_failures_repaired_at_least_one": (
            metrics["v6_top_failure_repaired"] >= 1
        ),
        "bottom_terminals_not_above_v6_reference": (
            candidate_v8.terminal_reasons.get("bottom", 0)
            <= reference_v6.terminal_reasons.get("bottom", 0)
        ),
    }


def _all(checks: dict[str, bool] | None) -> bool:
    return bool(checks) and all(checks.values())


def decide_v8_gate_status(
    *,
    source_checks: dict[str, bool],
    development_reachability_passed: bool | None,
    development_checks: dict[str, bool] | None,
    holdout_reachability_passed: bool | None,
    holdout_oracle_checks: dict[str, bool] | None,
    holdout_observable_checks: dict[str, bool] | None,
) -> str:
    if not _all(source_checks):
        return "FAIL_STOP_V8_SOURCE_INTEGRITY"
    if development_reachability_passed is not True or not _all(
        development_checks
    ):
        return "FAIL_STOP_V8_DEVELOPMENT"
    if holdout_reachability_passed is not True or not _all(
        holdout_oracle_checks
    ):
        return "FAIL_STOP_V8_HOLDOUT"
    if not _all(holdout_observable_checks):
        return "FAIL_STOP_ROUTE_INTENT_HOLDOUT"
    return "PASS_V8_ORACLE_AND_ROUTE_INTENT"


__all__ = [
    "ORACLE_V8_POLICY_VERSION",
    "create_terminal_guard_oracle",
    "decide_v8_gate_status",
    "edge_evaluation_from_dict",
    "paired_development_metrics",
    "terminal_audit_source_checks",
    "terminal_guard_oracle_factory",
    "v8_development_checks",
]
