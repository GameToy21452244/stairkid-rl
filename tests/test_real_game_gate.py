import numpy as np
import pytest

from stair_agent.observation import GameObservation
from stair_agent.input_controller import Action
from stair_agent.real_game_gate import (
    DirectionOscillationTracker,
    DropoutForensicRecorder,
    ObservationDropoutTracker,
    PhysicalResponseLatencyTracker,
    RealGameMicroLimits,
    SupportAlignedStallTracker,
    SupportDepartureTracker,
    apply_video_floor_maxima,
    classify_terminal_reason,
    dry_run_manifest,
    observation_confidence,
    outward_wall_push_side,
    playing_telemetry_required,
    reclassify_real_micro_episode,
    safe_unapplied_terminal,
    summarize_real_micro_gate,
)


def _observation(y=200.0, health=12, *, timestamp=1.0, velocity_x=0.0):
    return GameObservation(
        timestamp=timestamp,
        phase="playing",
        player={
            "center_y": y,
            "velocity_x": velocity_x,
            "confidence": 0.8,
        },
        health={"segments": health},
        nearest_platform=None,
        platforms=[{"confidence": 1.0}],
        platform_scroll_velocity_y=0.0,
        events=[],
    )


def _episode(floors, *, actions=None, terminal="bottom"):
    return {
        "steps": 10,
        "floors": floors,
        "action_counts": actions or {"LEFT": 4, "RIGHT": 3, "RELEASE_ALL": 3},
        "terminal_reason": terminal,
        "observation_valid": True,
        "observation_dropout_telemetry_available": True,
        "invalid_observation_step_count": 0,
        "max_recovered_observation_dropout_streak": 0,
        "unrecovered_observation_dropout_count": 0,
        "terminal_observation_dropout_count": 0,
        "blind_directional_action_count": 0,
        "top_pressure_dropout_continue_count": 0,
        "max_top_pressure_dropout_continue_streak": 0,
        "top_pressure_dropout_exhausted_count": 0,
        "top_pressure_support_escape_count": 0,
        "dropout_forensic_telemetry_available": True,
        "dropout_forensic_snapshot_count": 0,
        "dropout_forensic_dropped_snapshot_count": 0,
        "target_lock_seen": True,
        "transition_records": 10,
        "controller_records": 10,
        "video_complete": True,
        "physical_response_samples": [
            {"direction": "LEFT", "latency_ms": 100.0},
            {"direction": "RIGHT", "latency_ms": 125.0},
        ],
        "wall_telemetry_available": True,
        "outward_wall_push_count": 0,
        "max_outward_wall_push_streak": 0,
        "player_telemetry_available": True,
        "player_missing_step_count": 0,
        "max_player_missing_streak": 0,
        "wall_reentry_cycle_count": 0,
        "rapid_direction_reversal_count": 0,
        "max_rapid_direction_reversal_burst": 0,
        "max_wall_direction_reversal_burst": 0,
        "max_active_wall_direction_reversal_burst": 0,
        "max_aligned_release_streak": 2,
        "max_support_aligned_release_streak": 2,
        "max_actionable_support_aligned_release_streak": 0,
        "support_departure_telemetry_available": True,
        "support_edge_actionable_telemetry_available": True,
        "landing_intercept_telemetry_available": True,
        "landing_release_projection_telemetry_available": True,
        "special_escape_destination_telemetry_available": True,
        "special_contact_lifecycle_telemetry_available": True,
        "landing_intercept_decision_count": 1,
        "landing_release_projection_decision_count": 1,
        "destination_aware_special_escape_count": 0,
        "momentum_guard_special_escape_count": 0,
        "special_escape_replan_count": 0,
        "special_contact_count": 1,
        "pre_special_context_samples": [],
        "max_pre_special_observation_dropout_streak": 0,
        "max_pre_special_release_streak": 0,
        "max_pre_special_dropout_release_streak": 0,
        "spring_special_contact_count": 1,
        "spike_special_contact_count": 0,
        "special_source_reacquire_count": 0,
        "same_special_source_restart_count": 0,
        "max_special_contact_steps": 4,
        "max_special_escape_replan_count": 0,
        "max_special_direction_reversal_count": 0,
        "max_special_direction_change_brake_count": 0,
        "special_forced_exit_count": 0,
        "special_escape_safety_abort_count": 0,
        "same_support_departure_cycle_count": 0,
        "support_departure_target_switch_count": 0,
        "support_departure_timeout_count": 0,
        "support_departure_abort_cooldown_count": 0,
        "max_support_departure_abort_cooldown_streak": 0,
        "support_edge_release_count": 0,
        "support_edge_opportunity_count": 4,
        "support_departure_exit_samples": [3],
        "max_support_departure_steps": 3,
        "name_entry_dialog_detected": False,
        "name_entry_dialog_dismissed": False,
    }


def test_real_game_micro_limits_are_bounded() -> None:
    RealGameMicroLimits().validate()
    RealGameMicroLimits(
        episodes=10,
        max_total_steps=3000,
        max_total_seconds=600,
    ).validate()
    with pytest.raises(ValueError, match="3、5 或 10"):
        RealGameMicroLimits(episodes=11).validate()


def test_dry_run_never_claims_gate_pass() -> None:
    manifest = dry_run_manifest(RealGameMicroLimits())

    assert manifest["experiment"] == "teacher-real-game-micro-gate-v11"
    assert manifest["gate_status"] == "PENDING"
    assert manifest["safety"]["dry_run_loads_input_backend"] is False
    assert manifest["safety"]["dry_run_sends_input"] is False
    assert manifest["safety"]["inward_wall_guard_enabled"] is True
    assert "outward_wall_push_count" in manifest["required_gate_metrics"]
    assert "landing_intercept_decision_count" in manifest["required_gate_metrics"]
    assert "same_special_source_restart_count" in manifest["required_gate_metrics"]


def test_observation_confidence_uses_only_visible_detections() -> None:
    assert observation_confidence(_observation()) == pytest.approx(0.9)


def test_physical_latency_uses_first_motion_onset_after_direction_command() -> None:
    tracker = PhysicalResponseLatencyTracker(
        velocity_threshold=10.0,
        max_wait_seconds=0.5,
    )

    pending = tracker.update(
        Action.LEFT,
        command_timestamp=10.0,
        observation=_observation(timestamp=10.1, velocity_x=0.0),
    )
    detected = tracker.update(
        Action.LEFT,
        command_timestamp=10.12,
        observation=_observation(timestamp=10.2, velocity_x=-20.0),
    )

    assert pending.pending
    assert pending.latency_ms is None
    assert not detected.pending
    assert detected.direction == "LEFT"
    assert detected.latency_ms == pytest.approx(200.0)


def test_physical_latency_rejects_opposite_motion_and_release_clears() -> None:
    tracker = PhysicalResponseLatencyTracker(velocity_threshold=10.0)

    opposite = tracker.update(
        Action.RIGHT,
        command_timestamp=5.0,
        observation=_observation(timestamp=5.1, velocity_x=-30.0),
    )
    released = tracker.update(
        Action.RELEASE_ALL,
        command_timestamp=5.2,
        observation=_observation(timestamp=5.3, velocity_x=0.0),
    )

    assert opposite.pending
    assert opposite.latency_ms is None
    assert not released.pending
    assert released.latency_ms is None


def test_physical_latency_does_not_sample_preexisting_same_direction_motion() -> None:
    tracker = PhysicalResponseLatencyTracker(velocity_threshold=10.0)

    result = tracker.update(
        Action.RIGHT,
        command_timestamp=7.0,
        prior_observation=_observation(timestamp=6.9, velocity_x=25.0),
        observation=_observation(timestamp=7.1, velocity_x=30.0),
    )

    assert result.preexisting_motion
    assert result.latency_ms is None
    assert not result.pending


def test_terminal_reason_uses_last_playing_observation() -> None:
    assert classify_terminal_reason(
        _observation(y=400), forced_reason=None, reference_height=431
    ) == "bottom"
    assert classify_terminal_reason(
        _observation(y=20), forced_reason=None, reference_height=431
    ) == "top"
    assert classify_terminal_reason(
        _observation(health=0), forced_reason=None, reference_height=431
    ) == "health_depleted"


def test_unapplied_action_is_expected_only_after_terminal_phase_change() -> None:
    dialog = GameObservation(
        timestamp=2.0,
        phase="dialog",
        player=None,
        health={"segments": 0},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=[],
    )

    assert safe_unapplied_terminal(
        dialog,
        action_applied=False,
        terminated=True,
        truncated=False,
    )
    assert not safe_unapplied_terminal(
        _observation(),
        action_applied=False,
        terminated=False,
        truncated=False,
    )
    assert not safe_unapplied_terminal(
        dialog,
        action_applied=True,
        terminated=True,
        truncated=False,
    )


def test_terminal_dialog_does_not_require_playing_hud_telemetry() -> None:
    dialog = GameObservation(
        timestamp=2.0,
        phase="dialog",
        player=None,
        health={"segments": 0},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=[],
        floor={"value": None, "stable": False, "confidence": 0.0},
    )

    assert playing_telemetry_required(
        _observation(),
        terminated=False,
        truncated=False,
    )
    assert not playing_telemetry_required(
        dialog,
        terminated=True,
        truncated=False,
    )


def test_outward_wall_push_side_uses_actual_action_and_visible_player() -> None:
    assert outward_wall_push_side(
        Action.LEFT,
        player_x=55.0,
        playfield_left=40.0,
        playfield_right=423.0,
        margin=32.0,
    ) == "left"
    assert outward_wall_push_side(
        Action.RIGHT,
        player_x=410.0,
        playfield_left=40.0,
        playfield_right=423.0,
        margin=32.0,
    ) == "right"
    assert outward_wall_push_side(
        Action.RIGHT,
        player_x=200.0,
        playfield_left=40.0,
        playfield_right=423.0,
        margin=32.0,
    ) is None
    assert outward_wall_push_side(
        Action.LEFT,
        player_x=None,
        playfield_left=40.0,
        playfield_right=423.0,
        margin=32.0,
    ) is None


def test_real_micro_gate_reports_tail_metrics_and_passes_complete_smoke() -> None:
    summary = summarize_real_micro_gate(
        [_episode(2), _episode(5), _episode(8)],
        safety_events=[],
    )

    assert summary["metrics"]["floor_q25"] == pytest.approx(3.5)
    assert summary["metrics"]["floors_semantics"] == "visual_hud_max_floor"
    assert summary["metrics"]["floor_cvar25"] == pytest.approx(2.0)
    assert summary["metrics"]["reach_floor_5"] == 2
    assert summary["metrics"]["physical_response_sample_count"] == 6
    assert summary["gate"]["checks"]["physical_response_latency_measured"]
    assert summary["gate"]["passed"] is True


def test_real_micro_gate_rejects_action_collapse_or_missing_video() -> None:
    episodes = [_episode(5, actions={"RIGHT": 10}) for _ in range(3)]
    episodes[0]["video_complete"] = False

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["passed"] is False
    assert summary["gate"]["checks"]["no_action_collapse"] is False
    assert summary["gate"]["checks"]["videos_complete"] is False


def test_real_micro_gate_rejects_outward_wall_push_or_missing_telemetry() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["outward_wall_push_count"] = 2
    episodes[0]["max_outward_wall_push_streak"] = 2

    summary = summarize_real_micro_gate(episodes)

    assert summary["metrics"]["outward_wall_push_count"] == 2
    assert summary["metrics"]["max_outward_wall_push_streak"] == 2
    assert summary["gate"]["checks"]["outward_wall_push_zero"] is False
    assert summary["gate"]["passed"] is False

    episodes[0]["outward_wall_push_count"] = 0
    episodes[0]["max_outward_wall_push_streak"] = 0
    episodes[1]["wall_telemetry_available"] = False
    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["wall_telemetry_available"] is False
    assert summary["gate"]["passed"] is False


def test_direction_oscillation_tracker_detects_short_alternating_burst() -> None:
    tracker = DirectionOscillationTracker(max_step_gap=3)

    for step, action in enumerate(
        [
            Action.LEFT,
            Action.RELEASE_ALL,
            Action.RIGHT,
            Action.RELEASE_ALL,
            Action.LEFT,
            Action.RELEASE_ALL,
            Action.RIGHT,
        ]
    ):
        tracker.update(action, step=step)

    assert tracker.reversal_count == 3
    assert tracker.max_burst == 3


def test_direction_oscillation_tracker_excludes_special_escape_context() -> None:
    tracker = DirectionOscillationTracker(max_step_gap=3)

    tracker.update(Action.LEFT, step=10)
    tracker.update(Action.RIGHT, step=12, eligible=False)
    tracker.update(Action.LEFT, step=14)

    assert tracker.reversal_count == 0
    assert tracker.max_burst == 0


def test_observation_dropout_tracker_accepts_bounded_release_only_recovery() -> None:
    tracker = ObservationDropoutTracker(max_recoverable_steps=20)
    tracker.update(
        confidence=0.8,
        action=Action.LEFT,
        controller_phase="special_escape",
        floor=3,
    )
    for _ in range(15):
        tracker.update(
            confidence=0.0,
            action=Action.RELEASE_ALL,
            controller_phase="no_target",
            floor=3,
        )
    tracker.update(
        confidence=0.9,
        action=Action.LEFT,
        controller_phase="move",
        floor=4,
    )
    tracker.finalize(terminal=False)

    assert tracker.invalid_step_count == 15
    assert tracker.max_recovered_streak == 15
    assert tracker.recovered_count == 1
    assert tracker.unrecovered_count == 0
    assert tracker.blind_directional_action_count == 0
    assert tracker.recovery_samples[0]["context"] == "scroll_progress"


def test_observation_dropout_tracker_rejects_blind_action_or_unrecovered_gap() -> None:
    tracker = ObservationDropoutTracker(max_recoverable_steps=20)
    tracker.update(
        confidence=0.0,
        action=Action.RIGHT,
        controller_phase="no_target",
        floor=5,
    )
    tracker.finalize(terminal=False)

    assert tracker.blind_directional_action_count == 1
    assert tracker.unrecovered_count == 1


def test_observation_dropout_tracker_separates_bounded_top_pressure_action() -> None:
    tracker = ObservationDropoutTracker(max_recoverable_steps=20)
    for _ in range(2):
        tracker.update(
            confidence=0.0,
            action=Action.LEFT,
            controller_phase="top_pressure_escape",
            floor=5,
            approved_directional=True,
        )
    tracker.update(
        confidence=0.9,
        action=Action.LEFT,
        controller_phase="move",
        floor=5,
    )
    tracker.finalize(terminal=False)

    assert tracker.blind_directional_action_count == 0
    assert tracker.approved_directional_action_count == 2
    assert tracker.max_approved_directional_streak == 2


def test_support_aligned_stall_ignores_settle_but_detects_actionable_release() -> None:
    tracker = SupportAlignedStallTracker()
    settle = {
        "support_contact_active": True,
        "support_platform_id": 6,
        "target_platform_id": 6,
    }
    actionable = {
        **settle,
        "target_platform_id": 9,
    }

    for _ in range(4):
        tracker.update(
            settle,
            action=Action.RELEASE_ALL,
            reason="aligned_with_visible_safe_platform",
        )
    for _ in range(2):
        tracker.update(
            actionable,
            action=Action.RELEASE_ALL,
            reason="aligned_with_safe_platform",
        )

    assert tracker.support_settle_release_count == 4
    assert tracker.actionable_support_release_count == 2
    assert tracker.max_actionable_release_streak == 2


def test_reclassify_episode_separates_settle_dropout_and_special_wall_action() -> None:
    def record(
        step,
        action,
        reason,
        confidence,
        phase,
        *,
        support=6,
        target=6,
        wall=False,
        floor=3,
    ):
        return {
            "step": step,
            "action": action,
            "teacher_reason": reason,
            "observation_confidence": confidence,
            "floor": {"value": floor},
            "controller_memory": {
                "controller_phase": phase,
                "support_contact_active": support is not None,
                "support_platform_id": support,
                "target_platform_id": target,
                "wall_guard_active": wall,
                "wall_evacuation_active": False,
            },
        }

    rows = [
        record(
            0,
            "RELEASE_ALL",
            "aligned_with_visible_safe_platform",
            0.9,
            "aligned",
        ),
        record(
            1,
            "RIGHT",
            "escape_special_contact",
            0.8,
            "special_escape",
            wall=True,
        ),
        record(
            2,
            "RELEASE_ALL",
            "player_not_detected",
            0.0,
            "no_target",
            support=None,
            target=None,
        ),
        record(
            3,
            "LEFT",
            "move_toward_safe_platform",
            0.9,
            "move",
            support=None,
            target=9,
            floor=4,
        ),
    ]

    episode = reclassify_real_micro_episode(_episode(5), rows)

    assert episode["observation_valid"]
    assert episode["max_recovered_observation_dropout_streak"] == 1
    assert episode["blind_directional_action_count"] == 0
    assert episode["max_active_wall_direction_reversal_burst"] == 0
    assert episode["support_settle_release_count"] == 1
    assert episode["actionable_support_release_count"] == 0


def test_reclassify_episode_marks_release_only_terminal_gap_as_terminal() -> None:
    episode = _episode(5, terminal="bottom")
    rows = [
        {
            "step": 0,
            "action": "RELEASE_ALL",
            "teacher_reason": "player_not_detected",
            "observation_confidence": 0.0,
            "floor": {"value": 5},
            "controller_memory": {
                "controller_phase": "no_target",
                "support_contact_active": False,
                "support_platform_id": None,
                "target_platform_id": None,
                "wall_guard_active": False,
                "wall_evacuation_active": False,
            },
        }
    ]

    classified = reclassify_real_micro_episode(episode, rows)

    assert classified["terminal_observation_dropout_count"] == 1
    assert classified["unrecovered_observation_dropout_count"] == 0
    assert classified["blind_directional_action_count"] == 0
    assert classified["observation_valid"]


def test_reclassify_episode_tracks_semantic_special_contact_lifecycle() -> None:
    def row(
        step: int,
        *,
        source_id: int,
        escape_steps: int,
        action: str = "LEFT",
        reason: str = "escape_special_contact",
        reacquire: int = 0,
        replan: int = 0,
        reversal: int = 0,
        forced: bool = False,
        abort: bool = False,
    ):
        return {
            "step": step,
            "action": action,
            "teacher_reason": reason,
            "observation_confidence": 0.9,
            "floor": {"value": 3},
            "controller_memory": {
                "controller_phase": "special_escape",
                "support_contact_active": False,
                "support_platform_id": None,
                "target_platform_id": None,
                "wall_guard_active": False,
                "wall_evacuation_active": False,
                "landing_prediction_seconds": None,
                "landing_projected_x": None,
                "landing_safe_left": None,
                "landing_safe_right": None,
                "special_escape_direction_source": "nearest_edge",
                "special_escape_destination_platform_id": None,
                "special_escape_replanned": replan > 0,
                "special_contact_episode_id": 1,
                "special_source_platform_id": source_id,
                "special_source_platform_kind": "spring",
                "special_source_reacquire_count": reacquire,
                "special_escape_steps": escape_steps,
                "special_escape_replan_count": replan,
                "special_escape_direction_reversal_count": reversal,
                "special_escape_forced_exit_active": forced,
                "special_escape_safety_abort_active": abort,
                "special_escape_safety_abort_count": int(abort),
                "same_special_source_restart_count": 0,
            },
        }

    classified = reclassify_real_micro_episode(
        _episode(5),
        [
            row(0, source_id=27, escape_steps=1),
            row(
                1,
                source_id=30,
                escape_steps=2,
                action="RELEASE_ALL",
                reason="direction_change_brake",
                reacquire=1,
                replan=1,
                reversal=1,
            ),
            row(
                2,
                source_id=30,
                escape_steps=16,
                action="RELEASE_ALL",
                reason="special_escape_safety_abort",
                reacquire=1,
                replan=1,
                reversal=1,
                forced=True,
                abort=True,
            ),
        ],
    )

    assert classified["special_contact_lifecycle_telemetry_available"]
    assert classified["special_contact_count"] == 1
    assert classified["spring_special_contact_count"] == 1
    assert classified["special_source_reacquire_count"] == 1
    assert classified["max_special_contact_steps"] == 16
    assert classified["max_special_escape_replan_count"] == 1
    assert classified["max_special_direction_reversal_count"] == 1
    assert classified["max_special_direction_change_brake_count"] == 1
    assert classified["special_forced_exit_count"] == 1
    assert classified["special_escape_safety_abort_count"] == 1


def test_reclassify_episode_exposes_release_dropout_before_special_contact() -> None:
    def row(step, *, confidence, action, reason, contact_id=None):
        return {
            "step": step,
            "action": action,
            "teacher_reason": reason,
            "observation_confidence": confidence,
            "floor": {"value": 3},
            "controller_memory": {
                "controller_phase": (
                    "special_escape" if contact_id is not None else "no_target"
                ),
                "support_contact_active": False,
                "support_platform_id": None,
                "target_platform_id": None,
                "wall_guard_active": False,
                "wall_evacuation_active": False,
                "landing_prediction_seconds": None,
                "landing_projected_x": None,
                "landing_safe_left": None,
                "landing_safe_right": None,
                "special_escape_direction_source": "nearest_edge",
                "special_escape_destination_platform_id": None,
                "special_escape_replanned": False,
                "special_contact_episode_id": contact_id,
                "special_source_platform_id": 9,
                "special_source_platform_kind": "spikes",
                "special_source_reacquire_count": 0,
                "special_escape_steps": int(contact_id is not None),
                "special_escape_replan_count": 0,
                "special_escape_direction_reversal_count": 0,
                "special_escape_forced_exit_active": False,
                "special_escape_safety_abort_active": False,
                "special_escape_safety_abort_count": 0,
                "same_special_source_restart_count": 0,
            },
        }

    classified = reclassify_real_micro_episode(
        _episode(5),
        [
            row(
                0,
                confidence=0.9,
                action="RIGHT",
                reason="move_toward_safe_platform",
            ),
            row(
                1,
                confidence=0.0,
                action="RELEASE_ALL",
                reason="player_not_detected",
            ),
            row(
                2,
                confidence=0.0,
                action="RELEASE_ALL",
                reason="player_not_detected",
            ),
            row(
                3,
                confidence=0.0,
                action="RELEASE_ALL",
                reason="player_not_detected",
            ),
            row(
                4,
                confidence=0.9,
                action="RIGHT",
                reason="escape_special_contact",
                contact_id=1,
            ),
        ],
    )

    assert classified["max_pre_special_observation_dropout_streak"] == 3
    assert classified["max_pre_special_release_streak"] == 3
    assert classified["max_pre_special_dropout_release_streak"] == 3
    assert classified["pre_special_context_samples"] == [
        {
            "step": 4,
            "contact_id": 1,
            "kind": "spikes",
            "dropout_steps": 3,
            "release_steps": 3,
            "dropout_release_steps": 3,
        }
    ]


def test_real_micro_gate_rejects_pre_special_hesitation_context() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["max_pre_special_observation_dropout_streak"] = 10
    episodes[0]["max_pre_special_release_streak"] = 10
    episodes[0]["max_pre_special_dropout_release_streak"] = 10

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"][
        "pre_special_observation_dropout_bounded"
    ] is False
    assert summary["gate"]["checks"][
        "pre_special_dropout_release_bounded"
    ] is False


def test_support_departure_tracker_separates_actionable_and_generic_edge_release() -> None:
    tracker = SupportDepartureTracker(edge_threshold_pixels=20.0)
    active = {
        "support_contact_active": True,
        "support_platform_id": 7,
        "support_edge_distance": 9.0,
        "support_departure_active": True,
        "support_departure_source_id": 7,
        "support_departure_destination_id": 9,
        "support_departure_steps": 1,
    }
    inactive = {
        **active,
        "support_departure_active": False,
        "support_departure_steps": 0,
    }

    tracker.update(active, action=Action.LEFT, reason="depart_support_platform")
    tracker.update(
        inactive,
        action=Action.RELEASE_ALL,
        reason="aligned_with_safe_platform",
    )
    tracker.update(active, action=Action.LEFT, reason="depart_support_platform")

    assert tracker.same_support_departure_cycle_count == 1
    assert tracker.support_edge_release_count == 0
    assert tracker.support_edge_opportunity_count == 2
    assert tracker.generic_support_edge_release_count == 1
    assert tracker.generic_support_edge_opportunity_count == 3


def test_support_departure_tracker_excludes_same_support_settle_at_edge() -> None:
    tracker = SupportDepartureTracker(edge_threshold_pixels=20.0)
    same_support_settle = {
        "support_contact_active": True,
        "support_platform_id": 7,
        "support_edge_distance": 9.0,
        "target_platform_id": 7,
        "support_departure_active": False,
        "support_departure_destination_id": None,
        "support_departure_steps": 0,
    }

    tracker.update(
        same_support_settle,
        action=Action.RELEASE_ALL,
        reason="aligned_with_visible_safe_platform",
    )

    assert tracker.support_edge_release_count == 0
    assert tracker.support_edge_opportunity_count == 0
    assert tracker.generic_support_edge_release_count == 1
    assert tracker.generic_support_edge_opportunity_count == 1


def test_support_departure_tracker_allows_new_target_after_support_exit() -> None:
    tracker = SupportDepartureTracker()
    first = {
        "support_contact_active": True,
        "support_platform_id": 7,
        "support_edge_distance": 30.0,
        "support_departure_active": True,
        "support_departure_source_id": 7,
        "support_departure_destination_id": 9,
        "support_departure_steps": 3,
    }
    next_support = {
        **first,
        "support_platform_id": 9,
        "support_departure_source_id": 9,
        "support_departure_destination_id": 11,
        "support_departure_steps": 1,
    }

    tracker.update(first, action=Action.LEFT, reason="depart_support_platform")
    tracker.update(
        next_support,
        action=Action.RIGHT,
        reason="depart_support_platform",
    )

    assert tracker.support_departure_target_switch_count == 0
    assert tracker.support_departure_exit_samples == [3]


def test_real_micro_gate_rejects_support_departure_cycles_or_target_switches() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["same_support_departure_cycle_count"] = 1
    episodes[1]["support_departure_target_switch_count"] = 1
    episodes[2]["support_edge_release_count"] = 4
    episodes[2]["support_edge_opportunity_count"] = 4

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["same_support_departure_cycles_zero"] is False
    assert summary["gate"]["checks"]["support_departure_target_stable"] is False
    assert summary["gate"]["checks"]["support_edge_release_bounded"] is False
    assert summary["gate"]["passed"] is False


def test_real_micro_gate_requires_every_name_entry_dialog_to_be_dismissed() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[1]["name_entry_dialog_detected"] = True

    failed = summarize_real_micro_gate(episodes)

    assert failed["metrics"]["name_entry_dialog_detected_count"] == 1
    assert failed["metrics"]["name_entry_dialog_dismissed_count"] == 0
    assert failed["gate"]["checks"]["name_entry_dialogs_safely_handled"] is False

    episodes[1]["name_entry_dialog_dismissed"] = True
    passed = summarize_real_micro_gate(episodes)

    assert passed["gate"]["checks"]["name_entry_dialogs_safely_handled"] is True


def test_real_micro_gate_rejects_unbounded_departure_abort_cooldown() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["support_departure_abort_cooldown_count"] = 3
    episodes[0]["max_support_departure_abort_cooldown_streak"] = 3

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["support_departure_abort_cooldown_bounded"] is False


def test_real_micro_gate_requires_dropout_forensic_manifests() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[1]["dropout_forensic_telemetry_available"] = False

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["dropout_forensics_available"] is False


def test_real_micro_gate_requires_repair_v9_controller_telemetry() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["landing_intercept_telemetry_available"] = False
    episodes[1]["special_escape_destination_telemetry_available"] = False

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["landing_intercept_telemetry_available"] is False
    assert summary["gate"]["checks"]["special_escape_destination_telemetry_available"] is False


def test_real_micro_gate_requires_release_projection_telemetry() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["landing_release_projection_telemetry_available"] = False

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"][
        "landing_release_projection_telemetry_available"
    ] is False


def test_real_micro_gate_rejects_special_contact_restart_or_abort() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["same_special_source_restart_count"] = 1
    episodes[1]["special_escape_safety_abort_count"] = 1
    episodes[2]["max_special_direction_reversal_count"] = 2
    episodes[2]["max_special_direction_change_brake_count"] = 3

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["same_special_source_restarts_zero"] is False
    assert summary["gate"]["checks"]["special_escape_safety_aborts_zero"] is False
    assert summary["gate"]["checks"]["special_escape_replans_bounded"] is False
    assert summary["gate"]["checks"]["special_direction_change_brakes_bounded"] is False
    assert summary["gate"]["passed"] is False


def test_special_brake_budget_allows_entry_brake_plus_one_replan() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["max_special_direction_reversal_count"] = 1
    episodes[0]["max_special_escape_replan_count"] = 1
    episodes[0]["max_special_direction_change_brake_count"] = 2

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"][
        "special_direction_change_brakes_bounded"
    ] is True


def test_ten_episode_bottom_gate_only_counts_early_bottom_failures() -> None:
    floors = [8, 11, 4, 2, 2, 5, 4, 4, 8, 2]
    episodes = [_episode(value, terminal="bottom") for value in floors]
    episodes[1]["terminal_reason"] = "top"
    episodes[0]["spike_special_contact_count"] = 1

    allowed = summarize_real_micro_gate(episodes)

    assert allowed["metrics"]["bottom_death_count"] == 9
    assert allowed["metrics"]["early_bottom_death_count"] == 3
    assert allowed["gate"]["checks"]["early_bottom_deaths_bounded"] is True

    episodes[2]["floors"] = 2
    rejected = summarize_real_micro_gate(episodes)

    assert rejected["metrics"]["early_bottom_death_count"] == 4
    assert rejected["gate"]["checks"]["early_bottom_deaths_bounded"] is False


def test_video_floor_maxima_only_apply_evidence_backed_upward_correction() -> None:
    episodes = [{"episode": 1, "floors": 3, "floor_max": 3}]

    corrected = apply_video_floor_maxima(episodes, [4])

    assert corrected[0]["floors"] == 4
    assert corrected[0]["floor_max"] == 4
    assert corrected[0]["floor_max_sidecar"] == 3
    assert corrected[0]["floor_video_corrected"] is True
    assert episodes[0]["floors"] == 3

    with pytest.raises(ValueError, match="低於 sidecar"):
        apply_video_floor_maxima(episodes, [2])


def test_ten_episode_confirm_requires_both_special_kinds() -> None:
    episodes = [_episode(5, terminal="top") for _ in range(10)]
    episodes[1]["spring_special_contact_count"] = 0
    episodes[1]["spike_special_contact_count"] = 1

    covered = summarize_real_micro_gate(episodes)
    assert covered["gate"]["checks"]["ten_episode_special_kind_coverage"]
    assert covered["gate"]["passed"]

    episodes[1]["spike_special_contact_count"] = 0
    uncovered = summarize_real_micro_gate(episodes)
    assert uncovered["gate"]["checks"]["ten_episode_special_kind_coverage"] is False
    assert uncovered["gate"]["passed"] is False


def test_real_micro_gate_uses_actionable_support_aligned_streak() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["max_aligned_release_streak"] = 8
    episodes[0]["max_support_aligned_release_streak"] = 4

    settle_only = summarize_real_micro_gate(episodes)
    assert settle_only["gate"]["checks"]["actionable_support_release_zero"]

    episodes[0]["max_actionable_support_aligned_release_streak"] = 1
    support_stuck = summarize_real_micro_gate(episodes)
    assert support_stuck["gate"]["checks"]["actionable_support_release_zero"] is False


def test_real_micro_gate_rejects_vision_wall_cycles_and_early_bottom() -> None:
    episodes = [_episode(3), _episode(5), _episode(6)]
    episodes[0]["max_recovered_observation_dropout_streak"] = 21
    episodes[0]["blind_directional_action_count"] = 1
    episodes[1]["wall_reentry_cycle_count"] = 1
    episodes[2]["max_active_wall_direction_reversal_burst"] = 3
    episodes[0]["floors"] = 1
    episodes[0]["terminal_reason"] = "bottom"

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["recoverable_player_dropout_bounded"] is False
    assert summary["gate"]["checks"]["blind_directional_actions_zero"] is False
    assert summary["gate"]["checks"]["wall_reentry_cycles_zero"] is False
    assert summary["gate"]["checks"]["wall_safety_oscillation_bounded"] is False
    assert summary["gate"]["checks"]["floor_1_bottom_deaths_zero"] is False


def test_real_micro_gate_rejects_recovered_dropout_longer_than_eight_steps() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["max_recovered_observation_dropout_streak"] = 9

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["recoverable_player_dropout_bounded"] is False


def test_dropout_forensic_recorder_captures_bounded_milestones_and_recovery(
    tmp_path,
) -> None:
    frame = np.zeros((24, 32, 3), dtype=np.uint8)

    def diagnose(value):
        return (
            {"raw_colored_pixels": int(np.count_nonzero(value))},
            np.zeros(value.shape[:2], dtype=np.uint8),
        )

    recorder = DropoutForensicRecorder(
        tmp_path / "episode.dropout",
        diagnose_player=diagnose,
        milestones=(1, 3, 8),
        max_snapshots=4,
    )
    for step, source, streak in (
        (0, "tracked", 1),
        (1, "tracked", 2),
        (2, "missing", 3),
        (3, "missing", 4),
        (7, "missing", 8),
        (8, "raw", 0),
        (9, "missing", 1),
    ):
        recorder.observe(
            step=step,
            detection_source=source,
            missing_streak=streak,
            frame=frame,
            metadata={"reason": "test"},
        )
    manifest = recorder.finalize()

    assert [item["event"] for item in manifest["snapshots"]] == [
        "missing",
        "missing",
        "missing",
        "recovered",
    ]
    assert manifest["snapshot_count"] == 4
    assert manifest["dropped_snapshot_count"] == 1
    assert (tmp_path / "episode.dropout" / "manifest.json").is_file()
    assert all(
        (tmp_path / "episode.dropout" / item["raw_frame"]).is_file()
        for item in manifest["snapshots"]
    )
    assert all(
        (tmp_path / "episode.dropout" / item["player_mask"]).is_file()
        for item in manifest["snapshots"]
    )


def test_real_micro_gate_rejects_unbounded_or_exhausted_top_pressure_bridge() -> None:
    episodes = [_episode(5) for _ in range(3)]
    episodes[0]["top_pressure_dropout_continue_count"] = 3
    episodes[0]["max_top_pressure_dropout_continue_streak"] = 3
    episodes[1]["top_pressure_dropout_exhausted_count"] = 1

    summary = summarize_real_micro_gate(episodes)

    assert summary["gate"]["checks"]["top_pressure_continuation_bounded"] is False
    assert summary["gate"]["checks"]["top_pressure_dropout_exhaustion_zero"] is False
    assert summary["gate"]["passed"] is False
    assert summary["gate"]["passed"] is False
