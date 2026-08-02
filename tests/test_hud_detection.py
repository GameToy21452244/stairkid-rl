import numpy as np

from stair_agent.config import HudConfig
from stair_agent.hud_detection import (
    FloorCounterTracker,
    HealthEvent,
    HealthTracker,
    HudDetector,
)


def config():
    return HudConfig(
        reference_width=220,
        reference_height=160,
        life_left=10,
        life_top=5,
        life_segment_width=6,
        life_segment_height=14,
        life_segment_pitch=8,
        life_max_segments=12,
        life_filled_ratio=0.5,
    )


def health_frame(filled_segments):
    frame = np.zeros((160, 220, 3), dtype=np.uint8)
    for index in range(12):
        left = 10 + index * 8
        if index < filled_segments:
            frame[5:19, left : left + 6] = (0, 220, 255)
        else:
            frame[5:19, left : left + 6] = (20, 20, 80)
    return frame


def floor_config():
    return HudConfig(
        reference_width=100,
        reference_height=40,
        floor_counter_left=10,
        floor_counter_top=5,
        floor_counter_width=20,
        floor_counter_height=10,
        floor_counter_initial_value=1,
        floor_binary_threshold=120,
        floor_change_ratio_threshold=0.10,
        floor_stability_ratio_threshold=0.02,
        floor_change_required_consecutive=2,
    )


def floor_frame(columns):
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    for start, stop in columns:
        frame[5:15, 10 + start : 10 + stop] = 255
    return frame


def test_detects_filled_health_segments() -> None:
    detector = HudDetector(config())

    assert detector.detect_health(health_frame(12)).segments == 12
    assert detector.detect_health(health_frame(8)).segments == 8
    assert detector.detect_health(health_frame(5)).segments == 5


def test_health_tracker_reports_raw_delta() -> None:
    tracker = HealthTracker()

    initial = tracker.update(12)
    damaged = tracker.update(8)
    healed = tracker.update(9)
    unchanged = tracker.update(9)

    assert initial.event is HealthEvent.INITIALIZED
    assert damaged.delta == -4
    assert damaged.event is HealthEvent.DECREASED
    assert healed.delta == 1
    assert healed.event is HealthEvent.INCREASED
    assert unchanged.event is HealthEvent.UNCHANGED


def test_health_tracker_handles_missing_detection() -> None:
    tracker = HealthTracker()
    tracker.update(12)

    missing = tracker.update(None)
    returned = tracker.update(10)

    assert missing.event is HealthEvent.UNKNOWN
    assert returned.delta == -2


def test_floor_counter_confirms_only_stable_visual_change() -> None:
    tracker = FloorCounterTracker(floor_config())

    initial = tracker.update(floor_frame([(1, 3)]))
    animation_a = tracker.update(floor_frame([(1, 6)]))
    animation_b = tracker.update(floor_frame([(8, 14)]))
    candidate = tracker.update(floor_frame([(2, 8), (12, 15)]))
    confirmed = tracker.update(floor_frame([(2, 8), (12, 15)]))

    assert initial.value == 1
    assert initial.stable
    assert animation_a.delta is None and not animation_a.stable
    assert animation_b.delta is None and not animation_b.stable
    assert candidate.delta is None and not candidate.stable
    assert confirmed.value == 2
    assert confirmed.delta == 1
    assert confirmed.stable


def test_floor_counter_rejects_transient_flicker() -> None:
    tracker = FloorCounterTracker(floor_config())
    original = floor_frame([(1, 3)])

    tracker.update(original)
    pending = tracker.update(floor_frame([(5, 12)]))
    returned = tracker.update(original)

    assert pending.delta is None
    assert not pending.stable
    assert returned.value == 1
    assert returned.delta == 0
    assert returned.stable


def test_floor_counter_accepts_stable_three_percent_digit_change() -> None:
    calibrated = floor_config()
    calibrated.floor_change_ratio_threshold = 0.025
    tracker = FloorCounterTracker(calibrated)
    original = floor_frame([(1, 3)])
    subtle_change = original.copy()
    # Six of the 20x10 ROI pixels change: 3%, matching the real HUD 5->6
    # case (2.985%) that the previous 4% threshold could never confirm.
    subtle_change[5:7, 18:21] = 255

    tracker.update(original)
    candidate = tracker.update(subtle_change)
    confirmed = tracker.update(subtle_change)

    assert candidate.delta is None and not candidate.stable
    assert confirmed.value == 2
    assert confirmed.delta == 1
    assert confirmed.stable


def test_default_floor_change_threshold_covers_calibrated_five_to_six_delta() -> None:
    assert HudConfig().floor_change_ratio_threshold == 0.025


def test_floor_counter_reports_unavailable_without_calibrated_roi() -> None:
    tracker = FloorCounterTracker(HudConfig())

    result = tracker.update(np.zeros((40, 100, 3), dtype=np.uint8))

    assert result.value is None
    assert result.delta is None
    assert not result.stable
    assert result.confidence == 0.0
