from __future__ import annotations

import pytest

from stair_agent.training.p41_reanalysis import (
    risk_first_selected_updates,
    validate_selection_only_source,
)


def _candidate(update: int, *, bottom: float, reach: float) -> dict[str, object]:
    return {
        "update": update,
        "validation": {"loss": 0.5},
        "selection_rollout": {
            "collapsed": False,
            "health_death_rate": 0.0,
            "bottom_death_rate": bottom,
            "deepest_floor_quantile_25": 10.0,
            "deepest_floor_cvar25": 8.0,
            "reach_rate_floor_10": reach,
            "direction_reversals_per_100_steps": 1.0,
            "median_deepest_floor": 12.0,
            "mean_deepest_floor": 14.0,
        },
    }


def _summary() -> dict[str, object]:
    training = {}
    for variant in ("S0", "S1", "S2", "S3"):
        training[variant] = [
            {
                "initialization_seed": seed,
                "selected_update": 200,
                "candidates": [
                    _candidate(100, bottom=0.2, reach=0.95),
                    _candidate(200, bottom=0.1, reach=0.80),
                ],
            }
            for seed in (0, 1, 2)
        ]
    return {
        "experiment": "P4.1-bounded-S0-S1-S2-S3-ablation-v1",
        "status": "FAIL_STOP_SELECTION",
        "selected_architecture": None,
        "final_summaries": {},
        "final_gate_vs_s0": None,
        "manifest": {
            "dataset": {"sha256": "a" * 64},
            "protocol": {
                "selection_environment_seeds": list(range(4000, 4020)),
                "final_environment_seeds": list(range(4100, 4140)),
            },
        },
        "training": training,
    }


def test_reanalysis_uses_risk_first_candidate_selection() -> None:
    selected = risk_first_selected_updates(_summary())

    assert selected["S0"] == {0: 200, 1: 200, 2: 200}
    assert selected["S1"] == {0: 200, 1: 200, 2: 200}


def test_reanalysis_rejects_source_that_used_final_seeds() -> None:
    summary = _summary()
    summary["final_summaries"] = {"S0": [{"mean_deepest_floor": 1.0}]}

    with pytest.raises(ValueError, match="final"):
        validate_selection_only_source(summary)


def test_reanalysis_accepts_selection_fail_with_disjoint_seeds() -> None:
    validated = validate_selection_only_source(_summary())

    assert validated["dataset_sha256"] == "a" * 64
    assert validated["selection_seeds"] == tuple(range(4000, 4020))
    assert validated["final_seeds"] == tuple(range(4100, 4140))
