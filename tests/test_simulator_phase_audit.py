from stair_agent.data.simulator_phase_audit import (
    phase_signature,
    summarize_phase_observability,
)


def _sample(seed: int, outcome: str, *, velocity_y: float = -80.0):
    return {
        "seed": seed,
        "motion": "rising",
        "velocity_y": velocity_y,
        "nearest_gap": 5.0,
        "support_heuristic": True,
        "landed_event": False,
        "floor_descended_event": False,
        "edge_distance": 20.0,
        "nearest_platform_kind": "normal",
        "visible_platform_count": 4,
        "health_segments": 12,
        "steps_since_landing_event": 1,
        "intervention_outcome": outcome,
        "base_outcome": "target_reached",
        "base_reason": "aligned_with_safe_platform",
    }


def test_phase_signature_uses_only_deployable_bins() -> None:
    sample = _sample(1, "improved")

    signature = phase_signature(sample)

    assert signature == (
        "rising|strong_upward_screen|3_6|True|False|False|1_2|12_24|normal"
    )


def test_phase_audit_stops_when_intervention_evidence_is_too_small() -> None:
    divergences = [
        _sample(seed, "improved" if seed < 2 else "unchanged")
        for seed in range(60)
    ]

    result = summarize_phase_observability(divergences, list(divergences))

    assert result["status"] == "INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL"
    assert not result["evidence_sufficient"]
    assert not result["checks"]["changed_outcome_episodes_at_least_20"]


def test_phase_audit_rejects_same_signature_with_opposite_outcomes() -> None:
    divergences = [
        _sample(seed, "improved" if seed < 10 else "regressed")
        for seed in range(20)
    ]

    result = summarize_phase_observability(
        divergences,
        list(divergences),
        expected_episodes=20,
    )

    assert result["evidence_sufficient"]
    assert result["status"] == "FAIL_PHASE_SIGNATURE_ALIAS"
    assert result["improved_regressed_signature_conflicts"]
