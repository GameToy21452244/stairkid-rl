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
            platform(1, "spikes", 190, top=190),
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


def test_policy_releases_without_player_or_safe_target() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    missing_player = observation()
    missing_player = GameObservation(
        **{**missing_player.to_dict(), "player": None}
    )
    spikes_only = observation(
        platforms=[platform(1, "spikes", 100)]
    )

    assert policy.choose(missing_player).action is Action.RELEASE_ALL
    assert policy.choose(spikes_only).action is Action.RELEASE_ALL
