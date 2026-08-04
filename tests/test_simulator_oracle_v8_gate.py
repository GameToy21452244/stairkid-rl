from __future__ import annotations

from dataclasses import replace

from stair_agent.training.simulator_oracle_v8_gate import (
    create_terminal_guard_oracle,
    paired_development_metrics,
    terminal_audit_source_checks,
    v8_development_checks,
)
from stair_agent.training.simulator_v03_edge_gate import (
    EdgeEpisode,
    EdgeEvaluation,
)


def _evaluation(episodes: tuple[EdgeEpisode, ...]) -> EdgeEvaluation:
    reached = sum(item.deepest_floor >= 10 for item in episodes)
    return EdgeEvaluation(
        candidate="test",
        episodes=len(episodes),
        mean_deepest_floor=sum(item.deepest_floor for item in episodes)
        / len(episodes),
        reach_floor_3_rate=1.0,
        reach_floor_10_rate=reached / len(episodes),
        max_action_share=0.4,
        collapsed=False,
        action_counts={"RELEASE_ALL": 1, "LEFT": 1, "RIGHT": 1},
        support_departures=1,
        floor_descents=1,
        minimum_departure_clearance=0.0,
        invariant_violation_count=0,
        episodes_with_violations=0,
        terminal_reasons={
            "target_reached": reached,
            "bottom": sum(item.terminal_reason == "bottom" for item in episodes),
            "top": sum(item.terminal_reason == "top" for item in episodes),
        },
        episode_results=episodes,
    )


def _episode(seed: int, floor: int, terminal: str) -> EdgeEpisode:
    return EdgeEpisode(
        seed=seed,
        steps=1,
        deepest_floor=floor,
        terminal_reason=terminal,
        action_counts={"RELEASE_ALL": 1, "LEFT": 1, "RIGHT": 1},
        support_departures=0,
        floor_descents=0,
        minimum_departure_clearance=None,
        invariant_violations=(),
    )


def test_v8_factory_is_terminal_guard_only() -> None:
    oracle = create_terminal_guard_oracle()
    assert oracle.policy_version == "oracle-full-v8-terminal-risk-guard"
    assert oracle.route_plan_execution == "terminal_guarded"


def test_terminal_audit_source_checks_require_exact_separation() -> None:
    payload = {
        "status": "EVIDENCE_TERMINAL_RISK_ISOLATION",
        "holdout_used": False,
        "development_group_summaries": {
            "success": {"episodes": 96, "terminal_plan_exposed": 0},
            "top_failure": {"episodes": 2, "terminal_plan_exposed": 2},
            "bottom_failure": {"episodes": 2, "terminal_plan_exposed": 0},
        },
        "retired_search_failure_count": 3,
        "retired_search_failure_terminal_plan_exposed": 3,
        "evidence_checks": {"all": True},
    }
    assert all(terminal_audit_source_checks(payload).values())
    payload["development_group_summaries"]["success"][
        "terminal_plan_exposed"
    ] = 1
    assert not all(terminal_audit_source_checks(payload).values())


def test_v8_development_requires_no_regression_and_top_repair() -> None:
    reference = _evaluation((
        _episode(1, 10, "target_reached"),
        _episode(2, 5, "top"),
        _episode(3, 6, "bottom"),
    ))
    candidate = _evaluation((
        _episode(1, 10, "target_reached"),
        _episode(2, 10, "target_reached"),
        _episode(3, 6, "bottom"),
    ))
    metrics = paired_development_metrics(reference, candidate)
    assert metrics["v6_success_to_v8_failure"] == 0
    assert metrics["v6_top_failure_repaired"] == 1
    checks = v8_development_checks(reference, candidate)
    assert checks["v6_success_regressions_zero"]
    assert checks["v6_top_failures_repaired_at_least_one"]

    regressed_episodes = (
        _episode(1, 4, "bottom"),
        _episode(2, 10, "target_reached"),
        _episode(3, 6, "bottom"),
    )
    regressed = _evaluation(regressed_episodes)
    regressed = replace(regressed, reach_floor_10_rate=0.96)
    assert not v8_development_checks(
        reference,
        regressed,
    )["v6_success_regressions_zero"]

