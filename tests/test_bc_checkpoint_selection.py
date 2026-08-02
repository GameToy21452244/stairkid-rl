from __future__ import annotations

import pytest

from stair_agent.training.bc_checkpoint_selection import (
    checkpoint_gate_passed,
    checkpoint_selection_key,
    ensure_disjoint_seed_partitions,
)


def evaluation(
    mean_floors: float,
    *,
    collapsed: bool = False,
    bottom_deaths: int = 0,
    health_deaths: int = 0,
    floor_10_success: float = 1.0,
    floor_quantile_25: float | None = None,
    median_floors: float | None = None,
    deepest_floor_quantile_25: float | None = None,
    median_deepest_floor: float | None = None,
    mean_deepest_floor: float | None = None,
):
    q25 = mean_floors if floor_quantile_25 is None else floor_quantile_25
    median = mean_floors if median_floors is None else median_floors
    return {
        "mean_floors": mean_floors,
        "median_floors": median,
        "floor_quantile_25": q25,
        "mean_deepest_floor": (
            mean_floors
            if mean_deepest_floor is None
            else mean_deepest_floor
        ),
        "median_deepest_floor": (
            median
            if median_deepest_floor is None
            else median_deepest_floor
        ),
        "deepest_floor_quantile_25": (
            q25
            if deepest_floor_quantile_25 is None
            else deepest_floor_quantile_25
        ),
        "success_rate_floor_10": floor_10_success,
        "reach_rate_floor_10": floor_10_success,
        "collapsed": collapsed,
        "terminal_reasons": {
            "bottom": bottom_deaths,
            "health_depleted": health_deaths,
        },
    }


def test_seed_partitions_must_be_nonempty_and_disjoint() -> None:
    ensure_disjoint_seed_partitions(
        dataset_seeds=range(1000, 1060),
        selection_seeds=range(1060, 1080),
        final_seeds=range(1200, 1220),
    )
    with pytest.raises(ValueError, match="selection 與 final seeds 重疊"):
        ensure_disjoint_seed_partitions(
            dataset_seeds=[1],
            selection_seeds=[2, 3],
            final_seeds=[3, 4],
        )


def test_checkpoint_gate_uses_rollout_retention_and_safety() -> None:
    baseline = evaluation(30.0)
    random = evaluation(3.0)
    release = evaluation(7.0)
    assert checkpoint_gate_passed(
        evaluation=evaluation(25.0),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert not checkpoint_gate_passed(
        evaluation=evaluation(25.0, health_deaths=1),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert not checkpoint_gate_passed(
        evaluation=evaluation(20.0),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )


def test_rollout_floors_beat_lower_offline_validation_loss() -> None:
    baseline = evaluation(30.0)
    random = evaluation(3.0)
    release = evaluation(7.0)
    epoch_5 = checkpoint_selection_key(
        epoch=5,
        validation_loss=0.70,
        evaluation=evaluation(27.0, bottom_deaths=4),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    epoch_17 = checkpoint_selection_key(
        epoch=17,
        validation_loss=0.42,
        evaluation=evaluation(13.0, bottom_deaths=17),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert epoch_5 > epoch_17


def test_unsafe_checkpoint_cannot_win_on_mean_floors() -> None:
    baseline = evaluation(30.0)
    random = evaluation(3.0)
    release = evaluation(7.0)
    safe = checkpoint_selection_key(
        epoch=5,
        validation_loss=0.7,
        evaluation=evaluation(20.0),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    unsafe = checkpoint_selection_key(
        epoch=8,
        validation_loss=0.5,
        evaluation=evaluation(40.0, health_deaths=1),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert safe > unsafe


def test_reliability_beats_higher_mean_floors_during_selection() -> None:
    baseline = evaluation(
        30.0, floor_10_success=0.9, floor_quantile_25=20.0
    )
    random = evaluation(3.0, floor_10_success=0.0)
    release = evaluation(7.0, floor_10_success=0.2)
    reliable = checkpoint_selection_key(
        epoch=5,
        validation_loss=0.7,
        evaluation=evaluation(
            30.0,
            bottom_deaths=4,
            floor_10_success=0.9,
            floor_quantile_25=18.0,
            median_floors=29.0,
        ),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    high_mean_but_fragile = checkpoint_selection_key(
        epoch=8,
        validation_loss=0.5,
        evaluation=evaluation(
            45.0,
            bottom_deaths=10,
            floor_10_success=0.7,
            floor_quantile_25=4.0,
            median_floors=20.0,
        ),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert reliable > high_mean_but_fragile


def test_gate_rejects_bottom_death_and_floor10_reliability_regression() -> None:
    baseline = evaluation(
        30.0,
        bottom_deaths=6,
        floor_10_success=0.9,
        floor_quantile_25=20.0,
    )
    random = evaluation(3.0, floor_10_success=0.0)
    release = evaluation(7.0, floor_10_success=0.2)
    assert not checkpoint_gate_passed(
        evaluation=evaluation(
            40.0,
            bottom_deaths=7,
            floor_10_success=0.9,
            floor_quantile_25=20.0,
        ),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
    assert not checkpoint_gate_passed(
        evaluation=evaluation(
            40.0,
            bottom_deaths=5,
            floor_10_success=0.7,
            floor_quantile_25=20.0,
        ),
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )


def test_gate_prefers_deepest_floor_lower_tail_over_event_count() -> None:
    baseline = evaluation(30.0, deepest_floor_quantile_25=20.0)
    random = evaluation(3.0)
    release = evaluation(7.0)
    misleading_event_count = evaluation(
        30.0,
        floor_quantile_25=25.0,
        deepest_floor_quantile_25=10.0,
    )

    assert not checkpoint_gate_passed(
        evaluation=misleading_event_count,
        baseline=baseline,
        random=random,
        release=release,
        curriculum="spike-v0",
    )
