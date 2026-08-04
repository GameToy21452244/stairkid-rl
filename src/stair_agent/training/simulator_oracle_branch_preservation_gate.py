"""Frozen Gate helpers for the branch-preserving privileged Oracle."""

from __future__ import annotations

from typing import Iterable


PRIMARY_DEVELOPMENT_SEEDS = tuple(range(18000, 18100))
CONDITIONAL_DEVELOPMENT_EXTENSION = tuple(range(18100, 18200))
HOLDOUT_SEEDS = tuple(range(19000, 19100))
FORBIDDEN_SEEDS = frozenset(
    tuple(range(14000, 14100))
    + tuple(range(16000, 16100))
    + tuple(range(17000, 17100))
)
SWITCH_RATE_RELATIVE_LIMIT = 1.05


def validate_partition(role: str, seeds: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(int(seed) for seed in seeds)
    if set(normalized) & FORBIDDEN_SEEDS:
        raise ValueError("新candidate不得使用retired／v8 seed partition。")
    allowed = {
        "development": (PRIMARY_DEVELOPMENT_SEEDS,),
        "development_extended": (
            PRIMARY_DEVELOPMENT_SEEDS
            + CONDITIONAL_DEVELOPMENT_EXTENSION,
        ),
        "holdout": (HOLDOUT_SEEDS,),
    }
    if role not in allowed or normalized not in allowed[role]:
        raise ValueError(f"不合法的{role} seed partition。")
    if len(set(normalized)) != len(normalized):
        raise ValueError("seed partition不可重複。")
    return normalized


def select_development_seeds(
    *,
    v6_primary_top_failures: int,
) -> tuple[int, ...]:
    if int(v6_primary_top_failures) < 0:
        raise ValueError("v6 top failure count不可為負。")
    if int(v6_primary_top_failures) == 0:
        return PRIMARY_DEVELOPMENT_SEEDS + CONDITIONAL_DEVELOPMENT_EXTENSION
    return PRIMARY_DEVELOPMENT_SEEDS


def _switch_rate(metrics: dict[str, object]) -> float:
    return 100.0 * int(metrics["action_switch_count"]) / max(
        1,
        int(metrics["steps"]),
    )


def branch_preservation_development_checks(
    *,
    reference: dict[str, object],
    candidate: dict[str, object],
    v6_success_regressions: int,
    v6_top_failures: int,
    v6_top_failures_repaired: int,
    non_terminal_paths_identical: bool,
    reproducible: bool,
    planner_bounds_passed: bool,
) -> dict[str, bool]:
    return {
        "reach_floor_10_at_least_0.95": (
            float(candidate["reach_floor_10_rate"]) >= 0.95
        ),
        "reach_floor_10_not_below_v6": (
            float(candidate["reach_floor_10_rate"])
            >= float(reference["reach_floor_10_rate"])
        ),
        "v6_success_regressions_zero": int(v6_success_regressions) == 0,
        "v6_top_failure_evidence_exists": int(v6_top_failures) >= 1,
        "v6_top_failures_repaired_at_least_one": (
            int(v6_top_failures_repaired) >= 1
        ),
        "bottom_deaths_not_above_v6": (
            int(candidate["bottom_deaths"])
            <= int(reference["bottom_deaths"])
        ),
        "health_deaths_zero": int(candidate["health_deaths"]) == 0,
        "safety_violations_zero": (
            int(candidate["safety_violations"]) == 0
        ),
        "not_collapsed": not bool(candidate["collapsed"]),
        "non_terminal_paths_identical_to_v6": bool(
            non_terminal_paths_identical
        ),
        "action_switch_rate_inflation_at_most_5_percent": (
            _switch_rate(candidate)
            <= _switch_rate(reference) * SWITCH_RATE_RELATIVE_LIMIT + 1e-12
        ),
        "deterministic_duplicate_replay": bool(reproducible),
        "planner_bounds_pass": bool(planner_bounds_passed),
    }


def branch_preservation_holdout_checks(
    *,
    reference: dict[str, object],
    candidate: dict[str, object],
    reproducible: bool,
    planner_bounds_passed: bool,
) -> dict[str, bool]:
    return {
        "reach_floor_10_at_least_0.95": (
            float(candidate["reach_floor_10_rate"]) >= 0.95
        ),
        "reach_floor_10_not_below_v6": (
            float(candidate["reach_floor_10_rate"])
            >= float(reference["reach_floor_10_rate"])
        ),
        "bottom_deaths_not_above_v6": (
            int(candidate["bottom_deaths"])
            <= int(reference["bottom_deaths"])
        ),
        "health_deaths_zero": int(candidate["health_deaths"]) == 0,
        "safety_violations_zero": (
            int(candidate["safety_violations"]) == 0
        ),
        "not_collapsed": not bool(candidate["collapsed"]),
        "q25_not_below_v6": (
            float(candidate["q25"]) >= float(reference["q25"])
        ),
        "cvar25_not_below_v6": (
            float(candidate["cvar25"]) >= float(reference["cvar25"])
        ),
        "action_switch_rate_inflation_at_most_5_percent": (
            _switch_rate(candidate)
            <= _switch_rate(reference) * SWITCH_RATE_RELATIVE_LIMIT + 1e-12
        ),
        "deterministic_duplicate_replay": bool(reproducible),
        "planner_bounds_pass": bool(planner_bounds_passed),
    }


def holdout_allowed(
    development_checks: dict[str, bool] | None,
) -> bool:
    return bool(development_checks) and all(development_checks.values())


def incomplete_stage_payload(
    *,
    stage: str,
    reason: str,
) -> dict[str, object]:
    return {
        "schema_version": "simulator-oracle-branch-preservation-incomplete-v1",
        "stage": str(stage),
        "status": "INCOMPLETE",
        "passed": False,
        "stop_reason": str(reason),
        "holdout": {
            "partition": "19000-19099",
            "used": False,
        },
        "training_started": False,
        "dataset_generated": False,
        "real_game_started": False,
    }


__all__ = [
    "CONDITIONAL_DEVELOPMENT_EXTENSION",
    "FORBIDDEN_SEEDS",
    "HOLDOUT_SEEDS",
    "PRIMARY_DEVELOPMENT_SEEDS",
    "branch_preservation_development_checks",
    "branch_preservation_holdout_checks",
    "holdout_allowed",
    "incomplete_stage_payload",
    "select_development_seeds",
    "validate_partition",
]
