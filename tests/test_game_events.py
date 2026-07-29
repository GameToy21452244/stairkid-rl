from stair_agent.game_events import (
    describe_event_zh,
    GameEvent,
    GameEventDetection,
    GameplayEventDetector,
    SpringBounceDetector,
)
from stair_agent.hud_detection import HealthEvent, HealthUpdate
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


def tracked_platform(kind, track_id):
    return PlatformDetection(
        BoundingBox(40, 80, 96, 16),
        kind,
        0.95,
        track_id=track_id,
    )


def test_second_distinct_landing_emits_floor_descended() -> None:
    detector = GameplayEventDetector(
        landing_contact_gap=4,
        spring_contact_gap=8,
    )
    first = tracked_platform(PlatformKind.NORMAL, 1)
    second = tracked_platform(PlatformKind.NORMAL, 2)
    detector.update(
        state(MotionState.FALLING, first, gap=3),
        HealthUpdate(12, 0, HealthEvent.UNCHANGED),
    )
    first_landing = detector.update(
        state(MotionState.STABLE, first, gap=0),
        HealthUpdate(12, 0, HealthEvent.UNCHANGED),
    )
    detector.update(
        state(MotionState.FALLING, second, gap=3),
        HealthUpdate(12, 0, HealthEvent.UNCHANGED),
    )
    second_landing = detector.update(
        state(MotionState.STABLE, second, gap=0),
        HealthUpdate(12, 0, HealthEvent.UNCHANGED),
    )

    assert [item.event for item in first_landing] == [GameEvent.LANDED]
    assert [item.event for item in second_landing] == [
        GameEvent.LANDED,
        GameEvent.FLOOR_DESCENDED,
    ]


def test_positive_health_delta_emits_health_gained() -> None:
    detector = GameplayEventDetector()

    events = detector.update(
        state(MotionState.STABLE, platform=None, gap=None),
        HealthUpdate(8, 1, HealthEvent.INCREASED),
    )

    assert [item.event for item in events] == [GameEvent.HEALTH_GAINED]


def test_spike_landing_correlates_net_minus_four_as_spike_damage() -> None:
    detector = GameplayEventDetector(
        landing_contact_gap=4,
        spring_contact_gap=8,
        correlation_frames=4,
    )
    spikes = tracked_platform(PlatformKind.SPIKES, 3)
    detector.update(
        state(MotionState.FALLING, spikes, gap=3),
        HealthUpdate(9, 0, HealthEvent.UNCHANGED),
    )
    detector.update(
        state(MotionState.STABLE, spikes, gap=0),
        HealthUpdate(9, 0, HealthEvent.UNCHANGED),
    )

    events = detector.update(
        state(MotionState.STABLE, platform=None, gap=None),
        HealthUpdate(5, -4, HealthEvent.DECREASED),
    )

    assert [item.event for item in events] == [GameEvent.SPIKE_DAMAGE]
    assert events[0].health_delta == -4


def test_unattributed_health_loss_remains_generic_damage() -> None:
    detector = GameplayEventDetector()

    events = detector.update(
        state(MotionState.STABLE, platform=None, gap=None),
        HealthUpdate(7, -5, HealthEvent.DECREASED),
    )

    assert [item.event for item in events] == [GameEvent.DAMAGE]


def test_gameplay_default_detects_observed_spring_gap_nine() -> None:
    detector = GameplayEventDetector()
    detector.update(
        state(MotionState.FALLING, SPRING, gap=9),
        HealthUpdate(8, 0, HealthEvent.UNCHANGED),
    )

    events = detector.update(
        state(MotionState.RISING, SPRING, gap=10),
        HealthUpdate(9, 1, HealthEvent.INCREASED),
    )

    assert GameEvent.SPRING_BOUNCE in [item.event for item in events]


def test_event_description_includes_source_platform_and_delta() -> None:
    platform = tracked_platform(PlatformKind.FLIPPING, 7)
    landing = GameEventDetection(GameEvent.FLOOR_DESCENDED, platform)
    damage = GameEventDetection(GameEvent.DAMAGE, health_delta=-5)

    assert describe_event_zh(landing) == "成功下降至新平台(flipping)"
    assert describe_event_zh(damage) == "受到未分類傷害(delta=-5)"
