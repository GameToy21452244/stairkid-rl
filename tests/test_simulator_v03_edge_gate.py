from __future__ import annotations

from stair_agent.training.simulator_v03_edge_gate import (
    edge_fidelity_config,
    evaluate_edge_candidate,
    oracle_factory,
    release_factory,
)


def test_release_rollout_never_earns_a_floor_without_edge_departure() -> None:
    result = evaluate_edge_candidate(
        "release-test",
        release_factory,
        seeds=range(3),
        max_episode_steps=50,
        target_floor=3,
        config=edge_fidelity_config(),
    )

    assert result.floor_descents == 0
    assert result.mean_deepest_floor == 0.0
    assert result.invariant_violation_count == 0


def test_oracle_small_sample_uses_valid_edge_departures() -> None:
    result = evaluate_edge_candidate(
        "oracle-test",
        oracle_factory,
        seeds=range(5),
        max_episode_steps=200,
        target_floor=3,
        config=edge_fidelity_config(),
    )

    assert result.reach_floor_3_rate == 1.0
    assert result.support_departures >= result.floor_descents
    assert result.minimum_departure_clearance is not None
    assert result.minimum_departure_clearance >= -1e-6
    assert result.invariant_violation_count == 0
