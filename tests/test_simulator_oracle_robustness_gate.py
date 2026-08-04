from __future__ import annotations

import pytest

from stair_agent.training.simulator_oracle_robustness_gate import (
    DEVELOPMENT_SEEDS,
    HOLDOUT_SEEDS,
    create_receding_route_planner_oracle,
    decide_gate_status,
    development_oracle_checks,
    taxonomy_source_checks,
)
from stair_agent.training.simulator_v03_edge_gate import EdgeEvaluation


def _evaluation(*, reach10: float) -> EdgeEvaluation:
    return EdgeEvaluation(
        candidate="test",
        episodes=100,
        mean_deepest_floor=10.0,
        reach_floor_3_rate=1.0,
        reach_floor_10_rate=reach10,
        max_action_share=0.4,
        collapsed=False,
        action_counts={"RELEASE_ALL": 1, "LEFT": 1, "RIGHT": 1},
        support_departures=1,
        floor_descents=1,
        minimum_departure_clearance=0.0,
        invariant_violation_count=0,
        episodes_with_violations=0,
        terminal_reasons={"target_reached": 100},
        episode_results=(),
    )


def _valid_taxonomy() -> dict[str, object]:
    return {
        "status": "EVIDENCE_OPEN_LOOP_PRIMARY",
        "formal_gate": False,
        "retired_diagnostic_seeds_only": True,
        "mode_reach_floor_10_counts_out_of_7": {
            "current_v6": 0,
            "receding_current_trigger": 4,
            "always_receding": 0,
            "extended_always_receding": 0,
        },
        "all_current_v6_failures_reproduced": True,
        "all_planner_calls_restored_state": True,
        "all_searches_within_fixed_bounds": True,
        "failure_results": [{"seed": seed} for seed in (
            14005,
            14013,
            14025,
            14057,
            14060,
            14061,
            14065,
        )],
    }


def test_new_seed_partitions_are_exact_and_disjoint() -> None:
    assert DEVELOPMENT_SEEDS == tuple(range(16000, 16100))
    assert HOLDOUT_SEEDS == tuple(range(17000, 17100))
    assert not set(DEVELOPMENT_SEEDS) & set(HOLDOUT_SEEDS)
    assert not set(range(13000, 14100)) & set(DEVELOPMENT_SEEDS)
    assert not set(range(13000, 14100)) & set(HOLDOUT_SEEDS)


def test_v7_factory_is_explicit_receding_candidate() -> None:
    oracle = create_receding_route_planner_oracle()
    assert oracle.policy_version == "oracle-full-v7-receding-route-planner"
    assert oracle.enable_route_planner
    assert oracle.route_plan_execution == "receding"


def test_taxonomy_source_integrity_is_exact() -> None:
    assert all(taxonomy_source_checks(_valid_taxonomy()).values())
    corrupted = _valid_taxonomy()
    corrupted["mode_reach_floor_10_counts_out_of_7"] = {
        "current_v6": 0,
        "receding_current_trigger": 5,
        "always_receding": 0,
        "extended_always_receding": 0,
    }
    assert not all(taxonomy_source_checks(corrupted).values())


def test_development_requires_absolute_and_v6_nonregression() -> None:
    reference = _evaluation(reach10=0.96)
    assert all(
        development_oracle_checks(
            reference,
            _evaluation(reach10=0.97),
        ).values()
    )
    checks = development_oracle_checks(
        reference,
        _evaluation(reach10=0.95),
    )
    assert checks["reach_floor_10_at_least_0.95"]
    assert not checks["reach_floor_10_not_below_v6_reference"]


@pytest.mark.parametrize(
    (
        "source",
        "dev_reach",
        "dev",
        "holdout_reach",
        "holdout_oracle",
        "candidate",
        "expected",
    ),
    [
        (False, None, None, None, None, None, "FAIL_STOP_SOURCE_INTEGRITY"),
        (True, False, None, None, None, None,
         "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"),
        (True, True, False, None, None, None,
         "FAIL_STOP_ORACLE_ROBUSTNESS_DEVELOPMENT"),
        (True, True, True, False, None, None,
         "FAIL_STOP_ORACLE_ROBUSTNESS_HOLDOUT"),
        (True, True, True, True, False, None,
         "FAIL_STOP_ORACLE_ROBUSTNESS_HOLDOUT"),
        (True, True, True, True, True, False,
         "FAIL_STOP_ROUTE_INTENT_HOLDOUT"),
        (True, True, True, True, True, True,
         "PASS_ORACLE_ROBUSTNESS_AND_ROUTE_INTENT"),
    ],
)
def test_gate_status_stops_at_first_failure(
    source: bool,
    dev_reach: bool | None,
    dev: bool | None,
    holdout_reach: bool | None,
    holdout_oracle: bool | None,
    candidate: bool | None,
    expected: str,
) -> None:
    checks = {"check": source}
    assert decide_gate_status(
        source_checks=checks,
        development_reachability_passed=dev_reach,
        development_checks=None if dev is None else {"check": dev},
        holdout_reachability_passed=holdout_reach,
        holdout_oracle_checks=(
            None if holdout_oracle is None else {"check": holdout_oracle}
        ),
        holdout_candidate_checks=(
            None if candidate is None else {"check": candidate}
        ),
    ) == expected
