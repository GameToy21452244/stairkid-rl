from stair_agent.game_events import GameEvent, SpringBounceDetector
from stair_agent.object_detection import (
    BoundingBox,
    PlatformDetection,
    PlatformKind,
    PlayerDetection,
)
from stair_agent.object_tracking import MotionState, PlayerTrackingState


SPRING = PlatformDetection(
    BoundingBox(40, 80, 96, 16),
    PlatformKind.SPRING,
    0.95,
)
PLAYER = PlayerDetection(BoundingBox(60, 53, 24, 27), 0.9)


def state(motion, platform=SPRING, gap=0):
    return PlayerTrackingState(
        player=PLAYER,
        velocity_x=0.0,
        velocity_y=10.0 if motion is MotionState.FALLING else -10.0,
        motion=motion,
        nearest_platform_below=platform,
        platform_vertical_gap=gap,
    )


def test_falling_contact_then_rising_emits_spring_bounce() -> None:
    detector = SpringBounceDetector(contact_gap=4, max_wait_frames=3)

    approaching = detector.update(state(MotionState.FALLING, gap=3))
    bounced = detector.update(state(MotionState.RISING, gap=8))

    assert approaching.event is GameEvent.NONE
    assert bounced.event is GameEvent.SPRING_BOUNCE
    assert bounced.source_platform is SPRING


def test_rising_without_prior_spring_contact_is_not_bounce() -> None:
    detector = SpringBounceDetector()

    result = detector.update(state(MotionState.RISING, platform=None, gap=None))

    assert result.event is GameEvent.NONE


def test_pending_spring_contact_expires() -> None:
    detector = SpringBounceDetector(contact_gap=4, max_wait_frames=2)
    detector.update(state(MotionState.FALLING, gap=2))
    detector.update(state(MotionState.FALLING, platform=None, gap=None))
    detector.update(state(MotionState.FALLING, platform=None, gap=None))

    result = detector.update(state(MotionState.RISING, platform=None, gap=None))

    assert result.event is GameEvent.NONE


def test_spring_bounce_has_cooldown_to_avoid_duplicate_events() -> None:
    detector = SpringBounceDetector(
        contact_gap=4,
        max_wait_frames=3,
        cooldown_frames=3,
    )
    detector.update(state(MotionState.FALLING, gap=2))
    first = detector.update(state(MotionState.RISING, gap=6))
    repeated = detector.update(state(MotionState.RISING, gap=9))

    assert first.event is GameEvent.SPRING_BOUNCE
    assert repeated.event is GameEvent.NONE
