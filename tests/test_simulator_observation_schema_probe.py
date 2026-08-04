from __future__ import annotations

import pytest

from stair_agent.data.simulator_observation_schema_probe import (
    build_feature_vector,
    summarize_observation_schema_probe,
)


def _row(seed: int, split: str, outcome: str, *, target_offset: float):
    return {
        "seed": seed,
        "split": split,
        "intervention_outcome": outcome,
        "motion": "rising",
        "velocity_x": 120.0,
        "velocity_y": -60.0,
        "nearest_gap": 8.0,
        "nearest_platform_kind": "normal",
        "support_heuristic": True,
        "landed_event": False,
        "floor_descended_event": False,
        "steps_since_landing_event": 1,
        "edge_distance": 10.0,
        "visible_platform_count": 4,
        "health_segments": 12,
        "shadow_action": 2,
        "causal_action_state": [0.0] * 9,
        "target_present": True,
        "target_matched": True,
        "target_signed_offset": target_offset,
        "target_center_delta": target_offset,
        "target_top_delta": 80.0,
        "target_safe_left_delta": target_offset - 20.0,
        "target_safe_right_delta": target_offset + 20.0,
        "target_platform_kind": "normal",
    }


def test_schema_probe_feature_vectors_are_finite_and_variant_scoped() -> None:
    row = _row(7000, "development", "improved", target_offset=-80.0)

    basic = build_feature_vector(row, "phase_basic")
    causal = build_feature_vector(row, "causal_action")
    target = build_feature_vector(row, "target_relative")
    combined = build_feature_vector(row, "combined")

    assert basic.ndim == 1
    assert len(causal) > len(basic)
    assert len(target) > len(basic)
    assert len(combined) == len(causal) + len(target) - len(basic)
    assert all(float(value) == pytest.approx(float(value)) for value in combined)


def test_schema_probe_stops_when_counterfactual_evidence_is_too_small() -> None:
    rows = [
        _row(
            7000 + index,
            "development" if index < 20 else "validation",
            "improved" if index < 2 else "unchanged",
            target_offset=-80.0,
        )
        for index in range(30)
    ]

    result = summarize_observation_schema_probe(rows, expected_episodes=30)

    assert result["status"] == "INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE"
    assert not result["evidence_sufficient"]
    assert not result["checks"]["changed_outcomes_at_least_40"]


def test_schema_probe_passes_only_when_target_schema_generalizes() -> None:
    rows = []
    seed = 7000
    for split, count_per_class in (
        ("development", 10),
        ("validation", 5),
        ("test", 5),
    ):
        for outcome, offset in (("improved", -100.0), ("regressed", 100.0)):
            for _ in range(count_per_class):
                rows.append(_row(seed, split, outcome, target_offset=offset))
                seed += 1

    result = summarize_observation_schema_probe(
        rows,
        expected_episodes=len(rows),
    )

    assert result["status"] == "PASS_OBSERVATION_SCHEMA_PROBE"
    assert result["passed"]
    assert result["metrics"]["combined"]["test"]["balanced_accuracy"] == 1.0
    assert (
        result["metrics"]["combined"]["test"]["balanced_accuracy"]
        > result["metrics"]["phase_basic"]["test"]["balanced_accuracy"]
    )
