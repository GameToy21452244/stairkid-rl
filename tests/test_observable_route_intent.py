from __future__ import annotations

from stair_agent.training.simulator_v03_edge_gate import (
    baseline_factory,
    edge_fidelity_config,
    evaluate_edge_candidate,
    observable_route_intent_factory,
)


def test_route_intent_repairs_fixed_early_top_failure() -> None:
    legacy = evaluate_edge_candidate(
        "legacy-center-support",
        baseline_factory,
        seeds=[13015],
        max_episode_steps=100,
        target_floor=3,
        config=edge_fidelity_config(),
    )
    candidate = evaluate_edge_candidate(
        "observable-route-intent",
        observable_route_intent_factory,
        seeds=[13015],
        max_episode_steps=100,
        target_floor=3,
        config=edge_fidelity_config(),
    )

    assert legacy.episode_results[0].deepest_floor == 1
    assert candidate.episode_results[0].deepest_floor >= 3
    assert candidate.invariant_violation_count == 0


def test_route_intent_micro_gate_has_no_early_collapse() -> None:
    result = evaluate_edge_candidate(
        "observable-route-intent-micro",
        observable_route_intent_factory,
        seeds=range(13000, 13010),
        max_episode_steps=150,
        target_floor=3,
        config=edge_fidelity_config(),
    )

    assert result.reach_floor_3_rate >= 0.9
    assert result.invariant_violation_count == 0
    assert not result.collapsed
