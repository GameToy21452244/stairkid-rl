from __future__ import annotations

from stair_agent.calibration_analysis import (
    FRAME_WIDTH,
    LANDING_GAP_PX,
    LATEST,
    REFERENCE_HEIGHT,
    REFERENCE_WIDTH,
    is_continuous_motion_transition,
    landing_metrics,
    predicts_landing,
    two_proportion_z,
)


def features(*, motion=1.0, relative_x=0.0, relative_top_px=15.0):
    values = [0.0] * (4 * FRAME_WIDTH)
    values[LATEST] = 1.0
    values[LATEST + 5] = motion
    base = LATEST + 16
    values[base] = 1.0
    values[base + 1] = relative_x / REFERENCE_WIDTH
    values[base + 2] = relative_top_px / REFERENCE_HEIGHT
    values[base + 3] = 96.0 / REFERENCE_WIDTH
    return values


def row(*, before_motion=1.0, after_motion=1.0, events=None, terminated=False):
    return {
        "observation": features(motion=before_motion),
        "next_observation": features(motion=after_motion),
        "events": events or [],
        "terminated": terminated,
        "observation_timestamp": 1.0,
        "next_observation_timestamp": 1.1,
    }


def test_continuous_transition_rejects_unlabelled_motion_boundary():
    assert is_continuous_motion_transition(row())
    assert not is_continuous_motion_transition(
        row(before_motion=1.0, after_motion=-1.0)
    )


def test_landing_prediction_uses_motion_gap_and_horizontal_overlap():
    assert predicts_landing(features())
    assert not predicts_landing(features(motion=-1.0))
    assert not predicts_landing(
        features(relative_top_px=LANDING_GAP_PX + 1)
    )
    assert not predicts_landing(features(relative_x=80.0))


def test_landing_metrics_include_death_misclassification():
    rows = [
        row(events=[{"type": "landed"}]),
        row(),
        row(before_motion=-1.0, events=[{"type": "landed"}]),
        row(terminated=True),
    ]

    result = landing_metrics(rows)

    assert result.true_positive == 1
    assert result.false_positive == 2
    assert result.false_negative == 1
    assert result.death_misclassifications == 1


def test_two_proportion_z_rejects_invalid_counts_and_matches_equal_rates():
    assert two_proportion_z(5, 10, 50, 100) == 0

    import pytest

    with pytest.raises(ValueError):
        two_proportion_z(11, 10, 5, 10)
