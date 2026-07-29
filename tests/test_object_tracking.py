from stair_agent.object_detection import (
    BoundingBox,
    GameObjects,
    PlatformDetection,
    PlatformKind,
    PlayerDetection,
)
from stair_agent.object_tracking import (
    MotionState,
    PlatformTracker,
    PlatformStabilizer,
    PlayerTracker,
)


PLAYFIELD = BoundingBox(0, 0, 200, 160)


def objects(player_box, platforms=None):
    return GameObjects(
        PlayerDetection(player_box, 1.0) if player_box else None,
        platforms or [],
        PLAYFIELD,
    )


def test_tracker_computes_velocity_and_falling_state() -> None:
    tracker = PlayerTracker(motion_threshold=2.0)
    tracker.update(objects(BoundingBox(50, 30, 20, 20)), timestamp=1.0)

    state = tracker.update(
        objects(BoundingBox(56, 40, 20, 20)),
        timestamp=2.0,
    )

    assert state.velocity_x == 6.0
    assert state.velocity_y == 10.0
    assert state.motion is MotionState.FALLING


def test_tracker_detects_rising_and_stable() -> None:
    tracker = PlayerTracker(motion_threshold=2.0)
    tracker.update(objects(BoundingBox(50, 40, 20, 20)), timestamp=1.0)
    rising = tracker.update(
        objects(BoundingBox(50, 30, 20, 20)),
        timestamp=2.0,
    )
    stable = tracker.update(
        objects(BoundingBox(50, 31, 20, 20)),
        timestamp=3.0,
    )

    assert rising.motion is MotionState.RISING
    assert stable.motion is MotionState.STABLE


def test_tracker_selects_nearest_overlapping_platform_below() -> None:
    near = PlatformDetection(
        BoundingBox(40, 80, 80, 12),
        PlatformKind.NORMAL,
        1.0,
    )
    far = PlatformDetection(
        BoundingBox(20, 130, 100, 12),
        PlatformKind.SPIKES,
        1.0,
    )
    side = PlatformDetection(
        BoundingBox(130, 65, 50, 12),
        PlatformKind.NORMAL,
        1.0,
    )
    tracker = PlayerTracker()

    state = tracker.update(
        objects(BoundingBox(50, 40, 20, 20), [far, side, near]),
        timestamp=1.0,
    )

    assert state.nearest_platform_below is near
    assert state.platform_vertical_gap == 20


def test_missing_player_resets_velocity_history() -> None:
    tracker = PlayerTracker()
    tracker.update(objects(BoundingBox(50, 40, 20, 20)), timestamp=1.0)
    missing = tracker.update(objects(None), timestamp=2.0)
    returned = tracker.update(
        objects(BoundingBox(80, 90, 20, 20)),
        timestamp=3.0,
    )

    assert missing.player is None
    assert returned.motion is MotionState.UNKNOWN
    assert returned.velocity_x == 0.0


def test_platform_stabilizer_bridges_short_animated_template_miss() -> None:
    conveyor = PlatformDetection(
        BoundingBox(40, 80, 80, 12),
        PlatformKind.CONVEYOR,
        0.95,
    )
    stabilizer = PlatformStabilizer(
        persistent_kinds={PlatformKind.CONVEYOR},
        persistence_frames=2,
    )

    first = stabilizer.update(objects(None, [conveyor]))
    one_miss = stabilizer.update(objects(None, []))
    two_misses = stabilizer.update(objects(None, []))
    expired = stabilizer.update(objects(None, []))

    assert first.platforms == [conveyor]
    assert len(one_miss.platforms) == 1
    assert len(two_misses.platforms) == 1
    assert expired.platforms == []


def test_platform_stabilizer_updates_position_when_detection_returns() -> None:
    first = PlatformDetection(
        BoundingBox(40, 80, 80, 12),
        PlatformKind.FLIPPING,
        0.95,
    )
    moved = PlatformDetection(
        BoundingBox(40, 77, 80, 12),
        PlatformKind.FLIPPING,
        0.96,
    )
    stabilizer = PlatformStabilizer(
        persistent_kinds={PlatformKind.FLIPPING},
        persistence_frames=2,
    )
    stabilizer.update(objects(None, [first]))

    result = stabilizer.update(objects(None, [moved]))

    assert result.platforms == [moved]


def test_platform_tracker_keeps_ids_and_estimates_upward_scroll() -> None:
    tracker = PlatformTracker(match_distance=20.0)
    first_platforms = [
        PlatformDetection(
            BoundingBox(20, 100, 80, 12),
            PlatformKind.NORMAL,
            0.99,
        ),
        PlatformDetection(
            BoundingBox(120, 140, 80, 12),
            PlatformKind.SPIKES,
            0.98,
        ),
    ]
    first = tracker.update(objects(None, first_platforms), timestamp=1.0)
    moved_platforms = [
        PlatformDetection(
            BoundingBox(20, 97, 80, 12),
            PlatformKind.NORMAL,
            0.99,
        ),
        PlatformDetection(
            BoundingBox(120, 137, 80, 12),
            PlatformKind.SPIKES,
            0.98,
        ),
    ]

    moved = tracker.update(objects(None, moved_platforms), timestamp=1.1)

    assert [item.track_id for item in first.objects.platforms] == [1, 2]
    assert [item.track_id for item in moved.objects.platforms] == [1, 2]
    assert round(moved.scroll_velocity_y) == -30
    assert moved.matched_platforms == 2


def test_platform_tracker_assigns_new_id_to_new_platform() -> None:
    tracker = PlatformTracker(match_distance=10.0)
    tracker.update(
        objects(
            None,
            [
                PlatformDetection(
                    BoundingBox(20, 100, 80, 12),
                    PlatformKind.NORMAL,
                    0.99,
                )
            ],
        ),
        timestamp=1.0,
    )

    result = tracker.update(
        objects(
            None,
            [
                PlatformDetection(
                    BoundingBox(140, 140, 50, 12),
                    PlatformKind.NORMAL,
                    0.99,
                )
            ],
        ),
        timestamp=2.0,
    )

    assert result.objects.platforms[0].track_id == 2
