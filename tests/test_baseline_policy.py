from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.input_controller import Action
from stair_agent.observation import GameObservation


def observation(*, player_x=200.0, platforms=None, motion="falling"):
    return GameObservation(
        timestamp=1.0,
        phase="playing",
        player={
            "center_x": player_x,
            "center_y": 150.0,
            "velocity_x": 0.0,
            "velocity_y": 30.0,
            "motion": motion,
            "confidence": 0.9,
        },
        health={"segments": 12, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=platforms or [],
        platform_scroll_velocity_y=0.0,
        events=[],
    )


def platform(track_id, kind, left, top=210, width=96):
    return {
        "track_id": track_id,
        "kind": kind,
        "confidence": 0.99,
        "box": {
            "left": left,
            "top": top,
            "width": width,
            "height": 16,
        },
    }


def test_policy_moves_toward_closest_safe_platform() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        platforms=[
            platform(1, "normal", 300, top=205),
            platform(2, "normal", 20, top=280),
        ]
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.target_platform_id == 1
    assert decision.reason == "move_toward_safe_platform"


def test_policy_avoids_spikes_even_when_closer() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        platforms=[
            platform(1, "spikes", 350, top=190),
            platform(2, "normal", 40, top=220),
        ]
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 2


def test_policy_releases_inside_horizontal_deadzone() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(horizontal_deadzone_pixels=12)
    )
    item = observation(platforms=[platform(3, "spring", 157)])

    decision = policy.choose(item)

    assert decision.action is Action.RELEASE_ALL
    assert decision.target_platform_id == 3
    assert decision.reason == "aligned_with_safe_platform"


def test_policy_releases_without_player_or_any_target() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    missing_player = observation()
    missing_player = GameObservation(
        **{**missing_player.to_dict(), "player": None}
    )
    no_platforms = observation()

    assert policy.choose(missing_player).action is Action.RELEASE_ALL
    assert policy.choose(no_platforms).action is Action.RELEASE_ALL


def test_policy_locks_target_id_instead_of_chasing_closer_candidate() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    first = observation(
        platforms=[
            platform(1, "normal", 300, top=205),
            platform(2, "normal", 20, top=230),
        ]
    )
    changed = observation(
        platforms=[
            platform(1, "normal", 300, top=230),
            platform(2, "normal", 20, top=190),
        ]
    )

    assert policy.choose(first).target_platform_id == 1
    decision = policy.choose(changed)

    assert decision.target_platform_id == 1
    assert decision.action is Action.RIGHT


def test_policy_inserts_release_frames_before_reversing_direction() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(direction_switch_release_frames=2)
    )
    right_target = observation(
        platforms=[platform(1, "normal", 300)]
    )
    left_target = observation(
        platforms=[platform(1, "normal", 20)]
    )

    assert policy.choose(right_target).action is Action.RIGHT
    assert policy.choose(left_target).action is Action.RELEASE_ALL
    assert policy.choose(left_target).action is Action.RELEASE_ALL
    assert policy.choose(left_target).action is Action.LEFT


def test_policy_actively_moves_away_from_nearby_spikes() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=200,
        platforms=[
            platform(1, "spikes", 170, top=190),
            platform(2, "normal", 300, top=220),
        ],
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 1
    assert decision.target_platform_kind == "spikes"
    assert decision.reason == "avoid_nearby_spikes"


def test_policy_reset_clears_target_and_direction_memory() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    policy.choose(observation(platforms=[platform(1, "normal", 300)]))

    policy.reset()
    decision = policy.choose(
        observation(platforms=[platform(2, "normal", 20)])
    )

    assert decision.target_platform_id == 2
    assert decision.action is Action.LEFT
