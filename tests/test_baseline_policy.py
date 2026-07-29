from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.input_controller import Action
from stair_agent.observation import GameObservation


def observation(
    *,
    player_x=200.0,
    player_y=150.0,
    velocity_x=0.0,
    platforms=None,
    motion="falling",
    health=12,
    events=None,
):
    return GameObservation(
        timestamp=1.0,
        phase="playing",
        player={
            "center_x": player_x,
            "center_y": player_y,
            "velocity_x": velocity_x,
            "velocity_y": 30.0,
            "motion": motion,
            "confidence": 0.9,
        },
        health={"segments": health, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=platforms or [],
        platform_scroll_velocity_y=0.0,
        events=events or [],
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


def test_policy_does_not_flee_spikes_toward_empty_side() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=200,
        platforms=[
            platform(1, "spikes", 150, top=190),
            platform(2, "normal", 40, top=220),
        ],
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 2
    assert decision.target_platform_kind == "normal"
    assert decision.reason == "move_toward_safe_platform"


def test_policy_uses_reachable_safe_platform_on_side_away_from_spikes() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=200,
        platforms=[
            platform(1, "spikes", 150, top=190),
            platform(2, "normal", 260, top=220),
        ],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.target_platform_id == 2


def test_policy_ignores_platform_beyond_horizontal_reach() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            reachability_base_pixels=20,
            reachability_per_vertical_pixel=0.5,
        )
    )
    item = observation(
        player_x=50,
        platforms=[
            platform(1, "normal", 300, top=190),
            platform(2, "normal", 80, top=230),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 2
    assert decision.action is Action.RIGHT


def test_policy_aims_for_nearest_safe_edge_not_platform_center() -> None:
    policy = SafePlatformPolicy(BaselineConfig(landing_margin_pixels=10))
    item = observation(
        player_x=200,
        platforms=[platform(1, "normal", 220, top=210, width=96)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.horizontal_delta == 30.0


def test_policy_can_accept_spike_landing_near_top_when_no_safe_ground() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            top_danger_player_y_threshold=120,
            emergency_spike_min_health_segments=6,
        )
    )
    item = observation(
        player_x=200,
        player_y=90,
        health=8,
        platforms=[platform(1, "spikes", 240, top=170)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.target_platform_id == 1
    assert decision.reason == "emergency_spike_landing"


def test_policy_prefers_deeper_safe_platform_near_top() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(top_danger_player_y_threshold=120)
    )
    item = observation(
        player_x=200,
        player_y=100,
        platforms=[
            platform(1, "conveyor", 157, top=170),
            platform(2, "normal", 80, top=280),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 2
    assert decision.action is Action.LEFT
    assert decision.reason == "move_toward_deeper_safe_platform"


def test_top_danger_balances_depth_against_horizontal_distance() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            top_danger_player_y_threshold=150,
            max_target_vertical_gap_pixels=260,
            deep_landing_horizontal_cost=0.75,
        )
    )
    item = observation(
        player_x=312,
        player_y=125,
        platforms=[
            platform(1, "normal", 40, top=370),
            platform(2, "normal", 296, top=330),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 2
    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "aligned_with_deeper_safe_platform"


def test_policy_will_not_accept_spike_landing_with_too_little_health() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            top_danger_player_y_threshold=120,
            emergency_spike_min_health_segments=6,
        )
    )
    item = observation(
        player_x=200,
        player_y=90,
        health=5,
        platforms=[platform(1, "spikes", 240, top=170)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "no_reachable_landing"


def test_policy_reset_clears_target_and_direction_memory() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    policy.choose(observation(platforms=[platform(1, "normal", 300)]))

    policy.reset()
    decision = policy.choose(
        observation(platforms=[platform(2, "normal", 20)])
    )

    assert decision.target_platform_id == 2
    assert decision.action is Action.LEFT


def test_rising_player_skips_launch_platform_and_targets_next_floor() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=200,
        player_y=150,
        motion="rising",
        platforms=[
            platform(1, "spring", 157, top=165),
            platform(2, "normal", 300, top=270),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 1
    assert decision.action is Action.LEFT
    assert decision.reason == "escape_launch_platform"


def test_policy_reacquires_same_spatial_target_when_track_id_changes() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    first = observation(
        platforms=[
            platform(1, "normal", 300, top=220),
            platform(2, "normal", 20, top=250),
        ]
    )
    changed_ids = observation(
        platforms=[
            platform(99, "normal", 304, top=205),
            platform(3, "normal", 20, top=190),
        ]
    )

    assert policy.choose(first).target_platform_id == 1
    decision = policy.choose(changed_ids)

    assert decision.target_platform_id == 99
    assert decision.action is Action.RIGHT


def test_rising_player_escapes_spring_when_no_next_platform_visible() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=200,
        player_y=150,
        motion="rising",
        platforms=[platform(1, "spring", 157, top=165)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 1
    assert decision.reason == "escape_launch_platform"


def test_rising_player_keeps_aligned_lower_safe_platform() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=268,
        player_y=269.5,
        motion="rising",
        platforms=[
            platform(15, "normal", 248, top=332),
            platform(17, "normal", 40, top=380),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 15
    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "aligned_with_safe_platform"


def test_rising_player_keeps_moving_until_clear_of_launch_platform() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_platform_vertical_gap_pixels=30,
            launch_escape_clearance_pixels=8,
        )
    )
    first = observation(
        player_x=200,
        player_y=195,
        velocity_x=20,
        motion="rising",
        platforms=[
            platform(1, "normal", 157, top=210),
            platform(2, "normal", 157, top=280),
        ],
    )
    second = observation(
        player_x=225,
        player_y=160,
        velocity_x=30,
        motion="rising",
        platforms=[platform(2, "normal", 157, top=250)],
    )

    first_decision = policy.choose(first)
    second_decision = policy.choose(second)

    assert first_decision.action is Action.LEFT
    assert first_decision.reason == "escape_launch_platform"
    assert second_decision.action is Action.LEFT
    assert second_decision.reason == "escape_launch_platform"


def test_launch_escape_ends_after_player_clears_platform_edge() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_platform_vertical_gap_pixels=30,
            launch_escape_clearance_pixels=8,
        )
    )
    launch = observation(
        player_x=200,
        player_y=195,
        velocity_x=20,
        motion="rising",
        platforms=[platform(1, "normal", 157, top=210)],
    )
    cleared = observation(
        player_x=270,
        player_y=160,
        velocity_x=30,
        motion="falling",
        platforms=[platform(2, "normal", 157, top=250)],
    )

    assert policy.choose(launch).reason == "escape_launch_platform"
    decision = policy.choose(cleared)

    assert decision.reason != "escape_launch_platform"


def test_launch_escape_uses_nearest_edge_even_if_velocity_points_far_side() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=180,
        player_y=195,
        velocity_x=-80,
        motion="rising",
        platforms=[platform(1, "normal", 100, top=210)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.reason == "escape_launch_platform"


def test_landing_replaces_stale_launch_platform_escape() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    old_launch = observation(
        player_x=180,
        player_y=195,
        velocity_x=80,
        motion="rising",
        platforms=[platform(1, "normal", 100, top=210)],
    )
    new_launch = observation(
        player_x=200,
        player_y=195,
        velocity_x=20,
        motion="rising",
        platforms=[platform(2, "normal", 157, top=210)],
        events=[{"type": "landed", "source_platform_id": 2}],
    )

    assert policy.choose(old_launch).action is Action.RIGHT
    braking = policy.choose(new_launch)
    decision = policy.choose(new_launch)

    assert braking.target_platform_id == 2
    assert decision.target_platform_id == 2
    assert decision.action is Action.LEFT


def test_policy_briefly_continues_escape_when_next_floor_not_visible() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_escape_clearance_pixels=8,
            post_launch_coast_frames=2,
        )
    )
    launch = observation(
        player_x=180,
        player_y=195,
        motion="rising",
        platforms=[platform(1, "normal", 100, top=210)],
    )
    cleared = observation(
        player_x=210,
        player_y=170,
        motion="falling",
        platforms=[],
    )

    assert policy.choose(launch).action is Action.RIGHT
    first = policy.choose(cleared)
    second = policy.choose(cleared)
    final = policy.choose(cleared)

    assert first.action is Action.RIGHT
    assert first.reason == "reposition_for_unseen_landing"
    assert second.action is Action.RIGHT
    assert second.reason == "reposition_for_unseen_landing"
    assert final.action is Action.RELEASE_ALL
    assert final.reason == "no_reachable_landing"


def test_unseen_landing_fallback_moves_back_toward_playfield_center() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_escape_clearance_pixels=8,
            post_launch_coast_frames=2,
            fallback_center_x_pixels=231.5,
        )
    )
    launch = observation(
        player_x=300,
        player_y=195,
        motion="rising",
        platforms=[platform(1, "normal", 250, top=210)],
    )
    cleared = observation(
        player_x=355,
        player_y=170,
        motion="falling",
        platforms=[],
    )

    assert policy.choose(launch).action is Action.RIGHT
    braking = policy.choose(cleared)
    decision = policy.choose(cleared)

    assert braking.action is Action.RELEASE_ALL
    assert braking.reason == "direction_change_brake"
    assert decision.action is Action.LEFT
    assert decision.reason == "reposition_for_unseen_landing"


def test_visible_landing_overrides_post_launch_coast() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_escape_clearance_pixels=8,
            post_launch_coast_frames=3,
        )
    )
    launch = observation(
        player_x=180,
        player_y=195,
        motion="rising",
        platforms=[platform(1, "normal", 100, top=210)],
    )
    target_visible = observation(
        player_x=210,
        player_y=170,
        motion="falling",
        platforms=[platform(2, "normal", 20, top=250)],
    )

    assert policy.choose(launch).action is Action.RIGHT
    decision = policy.choose(target_visible)

    assert decision.target_platform_id == 2
    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "direction_change_brake"


def test_falling_player_escapes_spikes_immediately_below() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(launch_platform_vertical_gap_pixels=30)
    )
    item = observation(
        player_x=200,
        player_y=150,
        motion="falling",
        platforms=[
            platform(1, "spikes", 157, top=175),
            platform(2, "normal", 157, top=230),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 1
    assert decision.target_platform_kind == "spikes"
    assert decision.action is Action.LEFT
    assert decision.reason == "escape_launch_platform"
