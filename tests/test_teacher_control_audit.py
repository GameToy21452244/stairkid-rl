from __future__ import annotations

from stair_agent.teacher_control_audit import (
    NormalTransition,
    aggregate_special_encounters,
    classify_action_regime,
    leave_one_episode_out,
    select_normal_transition,
)


def _features(*, x: float, vx: float, motion: float = 1.0) -> list[float]:
    values = [0.0] * 268
    latest = 3 * 67
    values[latest] = 1.0
    values[latest + 1] = x / 634.0
    values[latest + 2] = 200.0 / 431.0
    values[latest + 3] = vx / 500.0
    values[latest + 4] = 20.0 / 500.0
    values[latest + 5] = motion
    return values


def _transition(
    *,
    step: int = 1,
    action: int = 0,
    x: float = 200.0,
    vx: float = 40.0,
    next_x: float = 204.0,
    next_vx: float = 20.0,
) -> dict:
    return {
        "episode_id": "episode_01",
        "step": step,
        "action": action,
        "observation": _features(x=x, vx=vx),
        "next_observation": _features(x=next_x, vx=next_vx),
        "events": [],
        "terminated": False,
        "truncated": False,
        "observation_timestamp": 1.0 + step,
        "action_command_timestamp": 1.02 + step,
        "action_effective_timestamp": 1.03 + step,
        "next_observation_timestamp": 1.10 + step,
        "target_platform_kind": "normal",
    }


def _controller(*, special: bool = False, wall: bool = False) -> dict:
    return {
        "observation_confidence": 0.95,
        "player_detection_source": "raw",
        "player_missing_streak": 0,
        "wall_guard_active": wall,
        "wall_evacuation_active": False,
        "controller_memory": {
            "controller_phase": "special_escape" if special else "move",
            "special_escape_active": special,
            "special_source_platform_kind": "spring" if special else None,
            "target_platform_kind": "normal",
            "recovery_active": False,
        },
    }


def test_normal_transition_filter_is_strict_about_controller_context() -> None:
    selected = select_normal_transition(
        _transition(),
        _controller(),
        source="run-a/episode_01",
        previous_action=2,
    )

    assert selected is not None
    assert selected.regime == "first_release_after_right"
    assert select_normal_transition(
        _transition(),
        _controller(special=True),
        source="run-a/episode_01",
        previous_action=2,
    ) is None
    assert select_normal_transition(
        _transition(),
        _controller(wall=True),
        source="run-a/episode_01",
        previous_action=2,
    ) is None


def test_action_regime_distinguishes_release_hold_and_reverse_braking() -> None:
    assert classify_action_regime(0, 120.0, 2) == "first_release_after_right"
    assert classify_action_regime(0, 20.0, 0) == "repeated_release"
    assert classify_action_regime(1, 80.0, 2) == "left_reverse_braking"
    assert classify_action_regime(2, -80.0, 1) == "right_reverse_braking"
    assert classify_action_regime(1, -80.0, 1) == "left_hold"


def test_episode_held_out_action_model_beats_velocity_carry_forward() -> None:
    rows: list[NormalTransition] = []
    action_effect = {0: 0.0, 1: -60.0, 2: 60.0}
    for episode in range(4):
        previous_action = 0
        x = 180.0 + episode
        vx = 20.0
        for step in range(12):
            action = step % 3
            next_vx = 0.5 * vx + action_effect[action]
            dt = 0.1
            next_x = x + next_vx * dt
            rows.append(
                NormalTransition(
                    source=f"run/episode_{episode}",
                    step=step,
                    action=action,
                    previous_action=previous_action,
                    regime=classify_action_regime(action, vx, previous_action),
                    x=x,
                    vx=vx,
                    next_x=next_x,
                    next_vx=next_vx,
                    dt=dt,
                    observation_to_next_ms=100.0,
                    effective_to_next_ms=70.0,
                    processing_to_command_ms=20.0,
                )
            )
            previous_action = action
            x = next_x
            vx = next_vx

    result = leave_one_episode_out(rows)

    assert result["overall"]["samples"] == len(rows)
    assert result["overall"]["model_vx_mae"] < 1e-8
    assert (
        result["overall"]["model_x_mae"]
        < result["overall"]["carry_x_mae"]
    )
    assert result["rollouts"]["5"]["windows"] > 0


def _special_row(
    step: int,
    *,
    kind: str,
    contact: int,
    action: str = "LEFT",
    floor: int = 3,
    events: list[dict] | None = None,
) -> dict:
    return {
        "step": step,
        "action": action,
        "floor": {"value": floor},
        "controller_memory": {
            "special_contact_episode_id": contact,
            "special_source_platform_id": 10 + contact,
            "special_source_platform_kind": kind,
        },
        "events": events or [],
    }


def test_special_encounters_bridge_short_contact_id_gaps_and_keep_outcomes() -> None:
    rows = [
        _special_row(10, kind="spring", contact=1),
        _special_row(
            11,
            kind="spring",
            contact=1,
            events=[{"type": "spring_bounce"}],
        ),
        {"step": 12, "action": "RELEASE_ALL", "floor": {"value": 3}, "controller_memory": {}, "events": []},
        {"step": 13, "action": "RIGHT", "floor": {"value": 3}, "controller_memory": {}, "events": []},
        _special_row(14, kind="spring", contact=2, action="RIGHT"),
        {"step": 15, "action": "RIGHT", "floor": {"value": 4}, "controller_memory": {}, "events": []},
        _special_row(30, kind="spikes", contact=3),
        {"step": 31, "action": "RIGHT", "floor": {"value": 3}, "controller_memory": {}, "events": [{"type": "health_gained"}]},
    ]

    encounters = aggregate_special_encounters(
        rows,
        source="run/episode_01",
        max_inactive_gap_steps=5,
        outcome_window_steps=4,
    )

    assert len(encounters) == 2
    spring = encounters[0]
    assert spring["kind"] == "spring"
    assert spring["contact_ids"] == [1, 2]
    assert spring["bounce_count"] == 1
    assert spring["release_count"] == 1
    assert spring["floor_progress"] == 1
    assert spring["normal_landing_count"] == 0
    spike = encounters[1]
    assert spike["kind"] == "spikes"
    assert spike["health_gain_count"] == 1
