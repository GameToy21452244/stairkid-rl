from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.input_controller import Action
from stair_agent.observation import GameObservation


def observation(
    *,
    player_x=200.0,
    player_y=150.0,
    velocity_x=0.0,
    velocity_y=30.0,
    platforms=None,
    motion="falling",
    health=12,
    events=None,
    nearest_platform=None,
):
    return GameObservation(
        timestamp=1.0,
        phase="playing",
        player={
            "center_x": player_x,
            "center_y": player_y,
            "velocity_x": velocity_x,
            "velocity_y": velocity_y,
            "motion": motion,
            "confidence": 0.9,
        },
        health={"segments": health, "delta": 0, "event": "unchanged"},
        nearest_platform=nearest_platform,
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


def test_policy_memory_snapshot_tracks_deployable_target_and_resets() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(platforms=[platform(7, "normal", 300)])

    policy.choose(item)
    first = policy.memory_snapshot()
    policy.choose(item)
    second = policy.memory_snapshot()

    assert first["target_platform_id"] == 7
    assert first["target_lock_age_steps"] == 1
    assert second["target_lock_age_steps"] == 2
    assert second["controller_phase"] == "move"
    assert second["previous_action"] == "RIGHT"
    policy.reset()
    assert policy.memory_snapshot()["target_platform_id"] is None
    assert policy.memory_snapshot()["action_streak_steps"] == 0


def test_policy_memory_snapshot_exposes_brake_and_recovery() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(direction_switch_release_frames=1)
    )
    policy.choose(
        observation(
            health=7,
            platforms=[platform(1, "normal", 300)],
        )
    )
    decision = policy.choose(
        observation(
            health=7,
            platforms=[platform(2, "normal", 20)],
        )
    )
    memory = policy.memory_snapshot()

    assert decision.reason == "direction_change_brake"
    assert memory["controller_phase"] == "brake"
    assert memory["recovery_active"] is True
    assert memory["previous_action"] == "RELEASE_ALL"


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


def test_policy_approaches_visible_safe_platform_when_none_are_reachable() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            reachability_base_pixels=20,
            reachability_per_vertical_pixel=0.1,
        )
    )
    item = observation(
        player_x=50,
        platforms=[platform(1, "normal", 300, top=210)],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 1
    assert decision.action is Action.RIGHT
    assert decision.reason == "approach_visible_safe_platform"


def test_policy_approaches_survivable_spikes_instead_of_certain_fall() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            reachability_base_pixels=20,
            reachability_per_vertical_pixel=0.1,
            emergency_spike_min_health_segments=6,
        )
    )
    item = observation(
        player_x=50,
        player_y=180,
        health=8,
        platforms=[platform(1, "spikes", 300, top=230)],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 1
    assert decision.action is Action.RIGHT
    assert decision.reason == "approach_visible_emergency_spikes"


def test_policy_does_not_approach_spikes_with_insufficient_health() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            reachability_base_pixels=20,
            reachability_per_vertical_pixel=0.1,
            emergency_spike_min_health_segments=6,
        )
    )
    item = observation(
        player_x=50,
        player_y=180,
        health=5,
        platforms=[platform(1, "spikes", 300, top=230)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "no_reachable_landing"


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


def test_damaged_policy_prioritizes_nearest_normal_recovery_platform() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(top_danger_player_y_threshold=120)
    )
    item = observation(
        player_x=200,
        player_y=150,
        health=7,
        platforms=[
            platform(1, "normal", 240, top=180),
            platform(2, "normal", 80, top=280),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 1
    assert decision.action is Action.RIGHT
    assert decision.reason == "move_toward_recovery_platform"


def test_top_danger_prioritizes_deep_escape_over_nearest_recovery() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(top_danger_player_y_threshold=120)
    )
    item = observation(
        player_x=200,
        player_y=100,
        health=1,
        platforms=[
            platform(1, "normal", 190, top=170),
            platform(2, "normal", 300, top=280),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 2
    assert decision.action is Action.RIGHT
    assert decision.reason == "move_toward_deeper_safe_platform"


def test_damage_replaces_locked_non_healing_target_with_nearest_normal() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(top_danger_player_y_threshold=120)
    )
    full_health = observation(
        player_x=200,
        player_y=150,
        health=12,
        platforms=[
            platform(1, "spring", 240, top=180),
            platform(2, "normal", 80, top=280),
        ],
    )
    damaged = observation(
        player_x=200,
        player_y=150,
        health=7,
        platforms=full_health.platforms,
    )

    assert policy.choose(full_health).target_platform_id == 1
    braking = policy.choose(damaged)
    recovery = policy.choose(damaged)

    assert braking.target_platform_id == 2
    assert braking.reason == "direction_change_brake"
    assert recovery.target_platform_id == 2
    assert recovery.reason == "move_toward_recovery_platform"


def test_recovery_mode_only_treats_normal_platform_as_healing() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(top_danger_player_y_threshold=120)
    )
    item = observation(
        player_x=200,
        player_y=150,
        health=7,
        platforms=[
            platform(1, "conveyor", 240, top=180),
            platform(2, "normal", 80, top=280),
        ],
    )

    decision = policy.choose(item)

    assert decision.target_platform_id == 2
    assert decision.reason == "move_toward_recovery_platform"


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
    assert decision.action is Action.RIGHT
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


def test_launch_escape_moves_toward_visible_next_platform() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=365,
        player_y=195,
        health=7,
        motion="rising",
        platforms=[
            platform(1, "normal", 300, top=210),
            platform(2, "normal", 180, top=270),
        ],
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 1
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


def test_spring_event_starts_persistent_special_contact_escape() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    contact = observation(
        player_x=200,
        player_y=195,
        motion="rising",
        platforms=[
            platform(11, "spring", 157, top=210),
            platform(12, "normal", 157, top=280),
        ],
        events=[
            {
                "type": "spring_bounce",
                "source_platform_id": 11,
                "source_platform_kind": "spring",
            }
        ],
    )
    after_event = observation(
        player_x=190,
        player_y=160,
        motion="rising",
        platforms=[platform(12, "normal", 157, top=250)],
    )

    first = policy.choose(contact)
    second = policy.choose(after_event)

    assert first.action is Action.LEFT
    assert first.reason == "escape_special_contact"
    assert second.action is Action.LEFT
    assert second.reason == "escape_special_contact"
    memory = policy.memory_snapshot()
    assert memory["special_escape_active"] is True
    assert memory["special_source_platform_id"] == 11
    assert memory["special_source_platform_kind"] == "spring"


def test_spike_landing_escape_overrides_aligned_recovery_target() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    contact = observation(
        player_x=200,
        player_y=195,
        health=7,
        motion="rising",
        platforms=[
            platform(9, "spikes", 157, top=210),
            platform(10, "normal", 157, top=280),
        ],
        events=[
            {
                "type": "landed",
                "source_platform_id": 9,
                "source_platform_kind": "spikes",
            }
        ],
    )
    after_event = observation(
        player_x=190,
        player_y=170,
        health=7,
        motion="falling",
        platforms=[platform(10, "normal", 157, top=250)],
    )

    first = policy.choose(contact)
    second = policy.choose(after_event)

    assert first.action is Action.LEFT
    assert first.reason == "escape_special_contact"
    assert second.action is Action.LEFT
    assert second.reason == "escape_special_contact"


def test_stable_geometric_spike_contact_starts_escape_without_event_source() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    spike = platform(9, "spikes", 157, top=210)
    nearest = {**spike, "vertical_gap": 5.0}
    contact = observation(
        player_x=200,
        player_y=195,
        health=3,
        motion="stable",
        platforms=[
            spike,
            platform(10, "normal", 157, top=280),
        ],
        nearest_platform=nearest,
        events=[
            {
                "type": "damage",
                "source_platform_id": None,
                "source_platform_kind": None,
                "health_delta": -1,
            }
        ],
    )

    decision = policy.choose(contact)

    assert decision.action is Action.LEFT
    assert decision.reason == "escape_special_contact"
    assert decision.target_platform_id == 9
    assert decision.target_platform_kind == "spikes"
    assert policy.memory_snapshot()["special_escape_active"] is True


def test_close_geometric_spring_contact_starts_escape_without_bounce_event() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    spring = platform(14, "spring", 157, top=210)
    nearest = {**spring, "vertical_gap": 18.0}
    contact = observation(
        player_x=200,
        player_y=180,
        motion="falling",
        platforms=[
            spring,
            platform(15, "normal", 280, top=290),
        ],
        nearest_platform=nearest,
    )

    decision = policy.choose(contact)

    assert decision.action is Action.RIGHT
    assert decision.reason == "escape_special_contact"
    assert decision.target_platform_id == 14
    assert decision.target_platform_kind == "spring"
    assert policy.memory_snapshot()["special_escape_active"] is True


def test_stable_aligned_platform_gap_eventually_starts_edge_escape() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            aligned_platform_dwell_escape_steps=3,
            aligned_platform_dwell_gap_tolerance_pixels=3.0,
        )
    )
    stuck = observation(
        player_x=190,
        player_y=320,
        health=1,
        motion="rising",
        platforms=[platform(19, "normal", 104, top=376, width=95)],
    )

    assert policy.choose(stuck).action is Action.RELEASE_ALL
    assert policy.choose(stuck).action is Action.RELEASE_ALL
    decision = policy.choose(stuck)

    assert decision.action is Action.RIGHT
    assert decision.reason == "escape_launch_platform_dwell"
    assert decision.target_platform_id == 19


def test_changing_aligned_platform_gap_does_not_trigger_dwell_escape() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            aligned_platform_dwell_escape_steps=3,
            aligned_platform_dwell_gap_tolerance_pixels=3.0,
        )
    )

    decisions = [
        policy.choose(
            observation(
                player_x=190,
                player_y=150,
                platforms=[platform(19, "normal", 150, top=top)],
            )
        )
        for top in (210, 220, 230, 240)
    ]

    assert all(item.reason != "escape_launch_platform_dwell" for item in decisions)


def test_left_wall_guard_reverses_close_spring_escape_inward() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    spring = platform(14, "spring", 40, top=210)
    item = observation(
        player_x=50,
        player_y=180,
        motion="falling",
        platforms=[spring],
        nearest_platform={**spring, "vertical_gap": 18.0},
    )

    decision = policy.choose(item)
    memory = policy.memory_snapshot()

    assert decision.action is Action.RIGHT
    assert decision.reason == "wall_guard_inward"
    assert memory["wall_guard_active"] is True
    assert memory["wall_guard_side"] == "left"
    assert memory["wall_guard_original_action"] == "LEFT"


def test_right_wall_guard_reverses_close_spike_escape_inward() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    spikes = platform(15, "spikes", 327, top=210)
    item = observation(
        player_x=410,
        player_y=180,
        motion="falling",
        platforms=[spikes],
        nearest_platform={**spikes, "vertical_gap": 18.0},
    )

    decision = policy.choose(item)

    assert decision.action is Action.LEFT
    assert decision.reason == "wall_guard_inward"
    assert policy.memory_snapshot()["wall_guard_side"] == "right"


def test_wall_guard_covers_launch_escape() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    item = observation(
        player_x=50,
        player_y=195,
        motion="rising",
        platforms=[platform(3, "normal", 40, top=210)],
    )

    decision = policy.choose(item)

    assert decision.action is Action.RIGHT
    assert decision.reason == "wall_guard_inward"
    assert policy.memory_snapshot()["launch_active"] is False
    assert policy.memory_snapshot()["wall_evacuation_active"] is True


def test_wall_evacuation_is_latched_until_hysteresis_exit() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            wall_guard_margin_pixels=32,
            wall_evacuation_exit_margin_pixels=64,
        )
    )
    source = platform(3, "normal", 50, top=210)

    first = policy.choose(
        observation(
            player_x=50,
            player_y=195,
            motion="rising",
            platforms=[source],
        )
    )
    middle = policy.choose(
        observation(
            player_x=90,
            player_y=180,
            velocity_x=120,
            motion="rising",
            platforms=[source],
        )
    )
    exited = policy.choose(
        observation(
            player_x=110,
            player_y=170,
            velocity_x=100,
            motion="rising",
            platforms=[source],
        )
    )

    assert first.action is Action.RIGHT
    assert middle.action is Action.RIGHT
    assert middle.reason == "wall_guard_inward"
    assert policy.memory_snapshot()["wall_evacuation_active"] is False
    assert exited.action is not Action.LEFT


def test_wall_cooldown_continues_inward_instead_of_waiting_for_reentry() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            wall_guard_margin_pixels=32,
            wall_evacuation_exit_margin_pixels=64,
            wall_evacuation_cooldown_steps=4,
        )
    )
    left_target = platform(8, "normal", -60, top=230)

    entered = policy.choose(
        observation(
            player_x=50,
            player_y=150,
            platforms=[left_target],
        )
    )
    exited = policy.choose(
        observation(
            player_x=110,
            player_y=150,
            platforms=[left_target],
        )
    )
    cooldown = policy.choose(
        observation(
            player_x=120,
            player_y=150,
            platforms=[left_target],
        )
    )

    assert entered.action is Action.RIGHT
    assert entered.reason == "wall_guard_inward"
    assert exited.action is Action.RIGHT
    assert exited.reason == "wall_guard_cooldown"
    assert cooldown.action is Action.RIGHT
    assert cooldown.reason == "wall_guard_cooldown"
    assert policy.memory_snapshot()["wall_evacuation_active"] is False


def test_top_pressure_dropout_continues_last_safe_direction_for_two_steps() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            top_danger_player_y_threshold=140,
            top_pressure_memory_steps=4,
            top_pressure_dropout_continue_steps=2,
        )
    )
    danger = observation(
        player_x=200,
        player_y=100,
        platforms=[platform(11, "normal", 60, top=260)],
    )
    missing = GameObservation(
        **{**danger.to_dict(), "player": None}
    )

    initial = policy.choose(danger)
    first = policy.choose(missing)
    second = policy.choose(missing)
    exhausted = policy.choose(missing)

    assert initial.action is Action.LEFT
    assert [first.action, second.action] == [Action.LEFT, Action.LEFT]
    assert first.reason == "top_pressure_dropout_continue"
    assert second.reason == "top_pressure_dropout_continue"
    assert exhausted.action is Action.RELEASE_ALL
    assert exhausted.reason == "top_pressure_dropout_exhausted"
    memory = policy.memory_snapshot()
    assert memory["top_pressure_dropout_steps"] == 2
    assert memory["top_pressure_dropout_exhausted"] is True


def test_missing_player_without_recent_top_pressure_still_releases() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    safe = observation(
        player_x=200,
        player_y=220,
        platforms=[platform(11, "normal", 60, top=300)],
    )
    missing = GameObservation(**{**safe.to_dict(), "player": None})

    policy.choose(safe)
    decision = policy.choose(missing)

    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "player_not_detected"


def test_top_pressure_support_settle_escapes_before_generic_dwell_limit() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            top_danger_player_y_threshold=140,
            top_pressure_support_settle_steps=2,
            aligned_platform_dwell_escape_steps=10,
        )
    )
    support = platform(7, "normal", 157, top=115)
    danger = observation(
        player_x=200,
        player_y=100,
        motion="stable",
        platforms=[support],
        nearest_platform={**support, "vertical_gap": 5.0},
    )

    waiting = policy.choose(danger)
    escaping = policy.choose(danger)

    assert waiting.action is Action.RELEASE_ALL
    assert escaping.action in {Action.LEFT, Action.RIGHT}
    assert escaping.reason == "escape_top_pressure_support_dwell"
    assert policy.memory_snapshot()["top_pressure_support_settle_steps"] == 0


def test_wall_evacuation_anticipates_outward_velocity_before_guard_edge() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(wall_guard_velocity_lookahead_seconds=0.2)
    )
    source = platform(3, "normal", 50, top=210)

    decision = policy.choose(
        observation(
            player_x=89,
            player_y=180,
            velocity_x=-190,
            motion="rising",
            platforms=[source],
        )
    )

    assert decision.action is Action.RIGHT
    assert decision.reason == "wall_guard_inward"
    assert policy.memory_snapshot()["wall_evacuation_active"] is True


def test_launch_commit_replans_after_bounded_direction_steps() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            launch_commit_max_steps=3,
            launch_replan_cooldown_steps=2,
            landing_velocity_lookahead_seconds=0.25,
        )
    )
    source = platform(3, "normal", 180, top=340)
    target = platform(4, "normal", 280, top=405)
    rows = [
        observation(
            player_x=x,
            player_y=y,
            velocity_x=vx,
            motion="rising",
            platforms=[source, target],
        )
        for x, y, vx in (
            (232, 325, 0),
            (245, 313, 104),
            (265, 301, 160),
            (288, 292, 184),
        )
    ]

    decisions = [policy.choose(item) for item in rows]

    assert [item.action for item in decisions[:3]] == [
        Action.RIGHT,
        Action.RIGHT,
        Action.RIGHT,
    ]
    assert decisions[3].action is not Action.RIGHT
    assert policy.memory_snapshot()["launch_active"] is False


def test_release_projection_brakes_inside_landing_interval() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            landing_velocity_lookahead_seconds=0.3,
            landing_release_projection_seconds=0.05,
        )
    )
    target = platform(7, "normal", 270, top=300, width=60)

    decision = policy.choose(
        observation(
            player_x=300,
            player_y=220,
            velocity_x=180,
            motion="falling",
            platforms=[target],
        )
    )

    assert decision.action is Action.RELEASE_ALL
    assert decision.horizontal_delta is not None
    assert abs(decision.horizontal_delta) <= 12


def test_gate_v4_ep2_release_drag_requires_continued_left_control() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            landing_velocity_lookahead_seconds=0.25,
            landing_prediction_max_seconds=0.55,
            landing_release_projection_seconds=0.05,
            landing_vertical_speed_floor_pixels_per_second=80.0,
        )
    )
    target = platform(11, "flipping", 40, top=360, width=96)

    decision = policy.choose(
        observation(
            player_x=231,
            player_y=256.5,
            velocity_x=-208,
            velocity_y=-44,
            motion="rising",
            platforms=[target],
        )
    )
    memory = policy.memory_snapshot()

    assert decision.action is Action.LEFT
    assert decision.target_platform_id == 11
    assert memory["landing_prediction_seconds"] == 0.55
    assert memory["landing_safe_left"] <= memory["landing_projected_x"]
    assert memory["landing_projected_x"] <= memory["landing_safe_right"]
    assert memory["landing_release_projected_x"] > memory["landing_safe_right"]


def test_gate_v7_ep3_keeps_right_to_reach_spring_after_release_drag() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(landing_release_projection_seconds=0.05)
    )
    spring = platform(14, "spring", 232, top=368, width=96)

    decision = policy.choose(
        observation(
            player_x=202.5,
            player_y=318.5,
            velocity_x=144,
            velocity_y=476,
            motion="falling",
            platforms=[spring],
        )
    )
    memory = policy.memory_snapshot()

    assert decision.action is Action.RIGHT
    assert decision.horizontal_delta is not None
    assert decision.horizontal_delta > 12
    assert memory["landing_release_projection_seconds"] == 0.05
    assert memory["landing_release_projected_x"] == 209.7
    assert memory["landing_release_horizontal_delta"] > 30


def test_gate_v7_ep1_keeps_left_when_release_would_stop_short() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(landing_release_projection_seconds=0.05)
    )
    recovery = platform(13, "normal", 88, top=360, width=95)

    decision = policy.choose(
        observation(
            player_x=247,
            player_y=310,
            velocity_x=-166.7,
            velocity_y=120,
            motion="falling",
            health=4,
            platforms=[recovery],
        )
    )

    assert decision.action is Action.LEFT
    assert decision.reason == "move_toward_recovery_platform"
    assert decision.horizontal_delta is not None
    assert decision.horizontal_delta < -60


def test_special_escape_commits_existing_outward_edge_momentum() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(special_escape_edge_guard_pixels=12.0)
    )
    spring = platform(15, "spring", 136, top=372, width=96)

    decision = policy.choose(
        observation(
            player_x=228,
            player_y=350,
            velocity_x=120,
            velocity_y=160,
            motion="falling",
            platforms=[spring],
            nearest_platform={**spring, "vertical_gap": 10.0},
            events=[
                {
                    "type": "spring_bounce",
                    "source_platform_id": 15,
                    "source_platform_kind": "spring",
                }
            ],
        )
    )
    memory = policy.memory_snapshot()

    assert decision.action is Action.RIGHT
    assert decision.reason == "escape_special_contact"
    assert memory["special_escape_direction_source"] == "edge_momentum_commit"


def test_special_escape_prefers_visible_deeper_safe_landing() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    spring = platform(15, "spring", 136, top=350, width=96)
    deeper = platform(18, "flipping", 88, top=405, width=96)

    decision = policy.choose(
        observation(
            player_x=225,
            player_y=330,
            velocity_x=80,
            velocity_y=100,
            motion="falling",
            platforms=[spring, deeper],
            nearest_platform={**spring, "vertical_gap": 10.0},
            events=[
                {
                    "type": "spring_bounce",
                    "source_platform_id": 15,
                    "source_platform_kind": "spring",
                }
            ],
        )
    )
    memory = policy.memory_snapshot()

    assert decision.action is Action.LEFT
    assert memory["special_escape_direction_source"] == "visible_landing"
    assert memory["special_escape_destination_platform_id"] == 18


def test_support_contact_exposes_edge_and_aligned_release_streak() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    support = platform(9, "normal", 100, top=210, width=96)
    item = observation(
        player_x=108,
        player_y=180,
        motion="stable",
        platforms=[support],
        nearest_platform={**support, "vertical_gap": 1.0},
    )

    policy.choose(item)
    memory = policy.memory_snapshot()

    assert memory["support_contact_active"] is True
    assert memory["support_platform_id"] == 9
    assert memory["support_edge_distance"] == 8


def test_live_hesitation_replay_latches_departure_until_support_is_lost() -> None:
    """Regression for real run 050608 EP1 source #7 -> destination #9."""

    policy = SafePlatformPolicy(
        BaselineConfig(
            support_departure_max_steps=8,
            support_departure_lost_frames=1,
        )
    )
    source = platform(7, "normal", 157, top=210)
    destination = platform(9, "flipping", 157, top=280)

    decisions = []
    for player_x in (200, 184, 168):
        decisions.append(
            policy.choose(
                observation(
                    player_x=player_x,
                    player_y=195,
                    velocity_x=-120,
                    motion="rising",
                    platforms=[source, destination],
                    nearest_platform={**source, "vertical_gap": 5.0},
                )
            )
        )

    assert [item.action for item in decisions] == [
        Action.LEFT,
        Action.LEFT,
        Action.LEFT,
    ]
    assert all(item.reason == "depart_support_platform" for item in decisions)
    assert all(item.target_platform_id == 9 for item in decisions)
    memory = policy.memory_snapshot()
    assert memory["support_departure_active"] is True
    assert memory["support_departure_source_id"] == 7
    assert memory["support_departure_destination_id"] == 9
    assert memory["support_departure_direction"] == "LEFT"


def test_departure_keeps_destination_when_a_closer_target_appears() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    source = platform(22, "normal", 120, top=210)
    destination = platform(25, "normal", 20, top=290)
    first = observation(
        player_x=150,
        player_y=195,
        motion="rising",
        platforms=[source, destination],
        nearest_platform={**source, "vertical_gap": 5.0},
    )
    distractor = platform(26, "normal", 260, top=250)
    second = observation(
        player_x=135,
        player_y=185,
        motion="rising",
        platforms=[source, destination, distractor],
        nearest_platform={**source, "vertical_gap": 6.0},
    )

    started = policy.choose(first)
    continued = policy.choose(second)

    assert started.action is Action.LEFT
    assert continued.action is Action.LEFT
    assert started.target_platform_id == 25
    assert continued.target_platform_id == 25
    assert policy.memory_snapshot()["support_departure_destination_id"] == 25


def test_departure_hands_off_to_airborne_landing_after_support_loss() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            support_departure_lost_frames=1,
            launch_replan_cooldown_steps=2,
        )
    )
    source = platform(7, "normal", 157, top=210)
    destination = platform(9, "normal", 80, top=280)
    contact = observation(
        player_x=200,
        player_y=195,
        motion="rising",
        platforms=[source, destination],
        nearest_platform={**source, "vertical_gap": 5.0},
    )
    airborne = observation(
        player_x=170,
        player_y=175,
        velocity_x=-160,
        motion="falling",
        platforms=[source, destination],
        nearest_platform=None,
    )

    assert policy.choose(contact).reason == "depart_support_platform"
    handoff = policy.choose(airborne)

    assert handoff.reason != "depart_support_platform"
    assert handoff.target_platform_id == 9
    memory = policy.memory_snapshot()
    assert memory["support_departure_active"] is False
    assert memory["launch_replan_cooldown_steps"] > 0


def test_departure_timeout_uses_bounded_cooldown_then_retries() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            support_departure_max_steps=2,
            support_departure_abort_cooldown_steps=2,
        )
    )
    source = platform(19, "normal", 120, top=210)
    destination = platform(21, "normal", 260, top=280)
    item = observation(
        player_x=150,
        player_y=195,
        motion="stable",
        platforms=[source, destination],
        nearest_platform={**source, "vertical_gap": 5.0},
    )

    decisions = [policy.choose(item) for _ in range(6)]

    assert [decision.reason for decision in decisions] == [
        "depart_support_platform",
        "depart_support_platform",
        "support_departure_safety_abort",
        "support_departure_abort_cooldown",
        "support_departure_abort_cooldown",
        "depart_support_platform",
    ]
    assert decisions[-1].action is Action.RIGHT
    memory = policy.memory_snapshot()
    assert memory["support_departure_active"] is True
    assert memory["support_departure_abort_cooldown_steps"] == 0


def test_wall_guard_covers_aligned_dwell_escape() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(aligned_platform_dwell_escape_steps=2)
    )
    stuck = observation(
        player_x=410,
        player_y=320,
        health=1,
        motion="rising",
        platforms=[platform(19, "normal", 327, top=376, width=96)],
    )

    assert policy.choose(stuck).action is Action.RELEASE_ALL
    decision = policy.choose(stuck)

    assert decision.action is Action.LEFT
    assert decision.reason == "wall_guard_inward"


def test_wall_guard_direction_change_keeps_one_frame_brake() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(direction_switch_release_frames=1)
    )
    spring = platform(14, "spring", 40, top=210)
    away_from_wall = observation(
        player_x=75,
        player_y=180,
        motion="falling",
        platforms=[spring],
        nearest_platform={**spring, "vertical_gap": 18.0},
    )
    at_wall = observation(
        player_x=50,
        player_y=170,
        motion="rising",
        platforms=[spring],
        nearest_platform={**spring, "vertical_gap": 20.0},
    )

    assert policy.choose(away_from_wall).action is Action.LEFT
    braking = policy.choose(at_wall)
    inward = policy.choose(at_wall)

    assert braking.action is Action.RELEASE_ALL
    assert braking.reason == "direction_change_brake"
    assert inward.action is Action.RIGHT
    assert inward.reason == "wall_guard_inward"


def test_special_contact_escape_ends_after_clearing_source_edge() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(launch_escape_clearance_pixels=8)
    )
    contact = observation(
        player_x=200,
        player_y=195,
        platforms=[platform(9, "spikes", 157, top=210)],
        events=[
            {
                "type": "landed",
                "source_platform_id": 9,
                "source_platform_kind": "spikes",
            }
        ],
    )
    cleared = observation(
        player_x=140,
        player_y=170,
        platforms=[platform(10, "normal", 100, top=250)],
    )

    assert policy.choose(contact).reason == "escape_special_contact"
    decision = policy.choose(cleared)

    assert decision.reason != "escape_special_contact"
    assert policy.memory_snapshot()["special_escape_active"] is False


def test_normal_landing_clears_special_contact_escape() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    contact = observation(
        player_x=200,
        player_y=195,
        health=7,
        platforms=[platform(9, "spikes", 157, top=210)],
        events=[
            {
                "type": "landed",
                "source_platform_id": 9,
                "source_platform_kind": "spikes",
            }
        ],
    )
    recovered = observation(
        player_x=190,
        player_y=195,
        health=8,
        motion="stable",
        platforms=[
            platform(10, "normal", 157, top=210),
            platform(11, "normal", 157, top=280),
        ],
        events=[
            {
                "type": "landed",
                "source_platform_id": 10,
                "source_platform_kind": "normal",
            }
        ],
    )

    assert policy.choose(contact).reason == "escape_special_contact"
    decision = policy.choose(recovered)

    assert decision.reason != "escape_special_contact"
    assert policy.memory_snapshot()["special_escape_active"] is False


def test_special_contact_escape_has_a_hard_step_limit() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            special_contact_escape_max_steps=2,
            special_contact_forced_exit_steps=2,
        )
    )
    contact = observation(
        player_x=200,
        player_y=195,
        platforms=[platform(11, "spring", 157, top=210)],
        events=[
            {
                "type": "spring_bounce",
                "source_platform_id": 11,
                "source_platform_kind": "spring",
            }
        ],
    )
    still_blocked = observation(
        player_x=195,
        player_y=160,
        motion="rising",
        platforms=[platform(12, "normal", 157, top=250)],
    )

    assert policy.choose(contact).reason == "escape_special_contact"
    assert policy.choose(still_blocked).reason == "escape_special_contact"
    assert policy.choose(still_blocked).reason == (
        "escape_special_contact_forced_exit"
    )
    assert policy.choose(still_blocked).reason == (
        "escape_special_contact_forced_exit"
    )
    decision = policy.choose(still_blocked)

    assert decision.action is Action.RELEASE_ALL
    assert decision.reason == "special_escape_safety_abort"
    memory = policy.memory_snapshot()
    assert memory["special_escape_active"] is True
    assert memory["special_escape_safety_abort_active"] is True
    assert memory["special_escape_safety_abort_count"] == 1


def test_special_contact_track_id_churn_preserves_semantic_episode() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(special_contact_replan_limit=0)
    )

    def spring_contact(track_id: int, top: float):
        spring = platform(track_id, "spring", 248, top=top, width=96)
        return observation(
            player_x=296,
            player_y=top - 18,
            motion="rising",
            platforms=[spring],
            nearest_platform={**spring, "vertical_gap": 18.0},
            events=[
                {
                    "type": "spring_bounce",
                    "source_platform_id": track_id,
                    "source_platform_kind": "spring",
                }
            ],
        )

    policy.choose(spring_contact(27, 340))
    first = policy.memory_snapshot()
    policy.choose(spring_contact(30, 288))
    second = policy.memory_snapshot()
    policy.choose(spring_contact(34, 240))
    third = policy.memory_snapshot()

    assert first["special_contact_episode_id"] == 1
    assert second["special_contact_episode_id"] == 1
    assert third["special_contact_episode_id"] == 1
    assert [first["special_escape_steps"], second["special_escape_steps"], third["special_escape_steps"]] == [1, 2, 3]
    assert third["special_source_reacquire_count"] == 2
    assert third["special_escape_direction"] == first["special_escape_direction"]


def test_special_contact_allows_only_one_stable_destination_replan() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            special_contact_direction_commit_steps=3,
            special_contact_destination_stability_steps=2,
            special_contact_replan_limit=1,
        )
    )
    spring = platform(11, "spring", 157, top=210)
    contact = observation(
        player_x=200,
        player_y=190,
        motion="rising",
        platforms=[spring],
        nearest_platform={**spring, "vertical_gap": 10.0},
    )
    right_destination = platform(12, "normal", 260, top=270)
    prefer_right = observation(
        player_x=200,
        player_y=190,
        motion="rising",
        platforms=[spring, right_destination],
        nearest_platform={**spring, "vertical_gap": 10.0},
    )
    left_destination = platform(13, "normal", 40, top=270)
    prefer_left = observation(
        player_x=200,
        player_y=190,
        motion="rising",
        platforms=[spring, left_destination],
        nearest_platform={**spring, "vertical_gap": 10.0},
    )

    assert policy.choose(contact).action is Action.LEFT
    policy.choose(prefer_right)
    policy.choose(prefer_right)
    brake = policy.choose(prefer_right)
    assert brake.action is Action.RELEASE_ALL
    assert brake.reason == "direction_change_brake"
    assert policy.memory_snapshot()["special_escape_replan_count"] == 1
    assert policy.choose(prefer_right).action is Action.RIGHT
    for _ in range(3):
        policy.choose(prefer_left)
    memory = policy.memory_snapshot()

    assert memory["special_escape_replan_count"] == 1
    assert memory["special_escape_direction_reversal_count"] == 1
    assert memory["special_escape_direction"] == "RIGHT"


def test_special_contact_abort_cannot_restart_same_source() -> None:
    policy = SafePlatformPolicy(
        BaselineConfig(
            special_contact_escape_max_steps=1,
            special_contact_forced_exit_steps=1,
            special_contact_replan_limit=0,
        )
    )
    spring = platform(11, "spring", 157, top=210)
    contact = observation(
        player_x=200,
        player_y=190,
        platforms=[spring],
        nearest_platform={**spring, "vertical_gap": 10.0},
        events=[
            {
                "type": "spring_bounce",
                "source_platform_id": 11,
                "source_platform_kind": "spring",
            }
        ],
    )

    assert policy.choose(contact).reason == "escape_special_contact"
    assert policy.choose(contact).reason == "escape_special_contact_forced_exit"
    assert policy.choose(contact).reason == "special_escape_safety_abort"
    first_abort = policy.memory_snapshot()
    assert policy.choose(contact).reason == "special_escape_safety_abort"
    repeated = policy.memory_snapshot()

    assert repeated["special_contact_episode_id"] == first_abort["special_contact_episode_id"]
    assert repeated["special_escape_safety_abort_count"] == 1
    assert repeated["same_special_source_restart_count"] == 0


def test_gate_v6_spike_contact_uses_nearest_exit_over_launch_memory() -> None:
    """Regression for real Gate v6 EP1 step 20, source #13."""

    policy = SafePlatformPolicy(BaselineConfig())
    policy._launch_direction = Action.LEFT
    spikes = platform(13, "spikes", 88, top=372, width=96)
    contact = observation(
        player_x=192,
        player_y=339,
        velocity_x=-56,
        velocity_y=4,
        platforms=[spikes],
        nearest_platform={**spikes, "vertical_gap": 10.0},
        events=[
            {
                "type": "landed",
                "source_platform_id": 13,
                "source_platform_kind": "spikes",
            }
        ],
    )

    decision = policy.choose(contact)
    memory = policy.memory_snapshot()

    assert decision.action is Action.RIGHT
    assert decision.horizontal_delta == 8
    assert memory["special_escape_direction_source"] == "nearest_edge"


def test_special_event_reuses_last_visible_bounds_after_kind_changes() -> None:
    policy = SafePlatformPolicy(BaselineConfig())
    visible_spring = observation(
        player_x=200,
        player_y=180,
        motion="falling",
        platforms=[platform(11, "spring", 157, top=210)],
    )
    compressed_or_misclassified = observation(
        player_x=200,
        player_y=195,
        motion="rising",
        platforms=[
            platform(11, "normal", 157, top=210),
            platform(12, "normal", 157, top=280),
        ],
        events=[
            {
                "type": "spring_bounce",
                "source_platform_id": 11,
                "source_platform_kind": "spring",
            }
        ],
    )

    policy.choose(visible_spring)
    decision = policy.choose(compressed_or_misclassified)

    assert decision.action is not Action.RELEASE_ALL
    assert decision.reason == "escape_special_contact"
    assert decision.target_platform_kind == "spring"
