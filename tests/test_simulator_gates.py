from __future__ import annotations

from stair_agent.simulator.gates import (
    FAILURE_REASONS,
    evaluation_summary,
    lower_tail_mean,
    run_reachability_gate,
)
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.learnability import evaluate_candidate, release_selector


def test_easy_reachability_gate_is_reproducible() -> None:
    result = run_reachability_gate(25, config=ShaftEnvConfig(distribution="easy"))
    assert result.passed
    assert result.reproducible
    assert not result.unreachable_seeds
    assert result.lookahead == 3


def test_gate_summary_has_required_success_rates_and_bootstrap_ci() -> None:
    result = evaluate_candidate(
        "release",
        release_selector,
        seeds=[1, 2, 3],
        max_episode_steps=8,
    )
    summary = evaluation_summary(result)
    assert len(summary["floors_bootstrap_ci95"]) == 2
    assert "success_rate_floor_10" in summary
    assert "reach_rate_floor_10" in summary
    assert "mean_deepest_floor" in summary
    assert "floor_quantile_25" in summary
    assert "deepest_floor_cvar25" in summary
    assert "bottom_death_rate" in summary
    assert "direction_switches_per_100_steps" in summary
    assert "direction_reversals_per_100_steps" in summary
    assert {"top_death", "bottom_death", "timeout"} <= set(FAILURE_REASONS)


def test_lower_tail_mean_uses_exact_worst_fraction() -> None:
    assert lower_tail_mean([1, 2, 10, 20], fraction=0.25) == 1.0
    assert lower_tail_mean([1, 2, 3, 10, 20], fraction=0.25) == 1.5
