import numpy as np

from stair_agent.config import HudConfig
from stair_agent.hud_detection import HealthEvent, HealthTracker, HudDetector


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
