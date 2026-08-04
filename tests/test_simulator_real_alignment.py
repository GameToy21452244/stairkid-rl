from __future__ import annotations

from copy import deepcopy

from stair_agent.data.simulator_real_alignment import (
    analyze_alignment_records,
    collect_simulator_alignment_records,
    evaluate_simulator_real_alignment,
)
from stair_agent.policies.simulator_teachers import SIMULATOR_TEACHER_PROFILES
from stair_agent.simulator.state import ShaftEnvConfig


def _row(
    *,
    step: int,
    episode_id: str = "ep-1",
    action: str = "RIGHT",
    x: float = 100.0,
    next_x: float = 104.0,
    vx: float = 0.0,
    next_vx: float = 40.0,
    motion: str = "falling",
    support: bool = False,
    departure: bool = False,
    departure_steps: int = 0,
    reason: str = "move_toward_safe_platform",
    target_kind: str = "normal",
    source_kind: str | None = None,
    safe_left_delta: float = 10.0,
    safe_right_delta: float = 70.0,
) -> dict[str, object]:
    support_id = 7 if support else None
    memory = {
        "support_contact_active": support,
        "support_platform_id": support_id,
        "support_departure_active": departure,
        "support_departure_source_id": 7 if departure else None,
        "support_departure_source_kind": "normal" if departure else None,
        "support_departure_steps": departure_steps,
        "support_departure_direction": action if departure else None,
        "special_source_platform_kind": source_kind,
    }
    post = deepcopy(memory)
    if reason == "support_departure_safety_abort":
        post["support_departure_active"] = False
        post["support_departure_steps"] = 0
    action_value = {"RELEASE_ALL": 0, "LEFT": 1, "RIGHT": 2}[action]
    observation = {
        "timestamp": step * 0.1,
        "player": {
            "center_x": x,
            "center_y": 150.0,
            "velocity_x": vx,
            "velocity_y": -80.0 if motion == "rising" else 80.0,
            "motion": motion,
        },
        "nearest_platform": (
            {
                "track_id": support_id,
                "kind": "normal",
                "vertical_gap": 1.0,
                "box": {"left": 60.0, "top": 164.0, "width": 96.0, "height": 16.0},
            }
            if support
            else None
        ),
        "platforms": [],
    }
    next_observation = deepcopy(observation)
    next_observation["timestamp"] = (step + 1) * 0.1
    next_observation["player"]["center_x"] = next_x
    next_observation["player"]["velocity_x"] = next_vx
    return {
        "episode_id": episode_id,
        "step": step,
        "observation": observation,
        "next_observation": next_observation,
        "pre_decision_memory": memory,
        "post_decision_memory": post,
        "teacher": {
            "action": action_value,
            "action_name": action,
            "reason": reason,
            "target_platform_kind": target_kind,
        },
        "target_geometry": {
            "selected": True,
            "matched": True,
            "platform_id": 11,
            "kind": target_kind,
            "safe_left_delta": safe_left_delta,
            "safe_right_delta": safe_right_delta,
        },
        "timing": {
            "observation_timestamp": step * 0.1,
            "action_command_timestamp": step * 0.1 + 0.005,
            "action_effective_timestamp": step * 0.1 + 0.01,
            "next_observation_timestamp": (step + 1) * 0.1,
            "held_action": False,
            "action_duration_ms": 80.0,
        },
    }


def test_analyze_alignment_records_reports_response_and_conflicting_action() -> None:
    rows = [
        _row(step=0, action="RIGHT", next_vx=50.0),
        _row(
            step=1,
            action="LEFT",
            x=104.0,
            next_x=101.0,
            vx=50.0,
            next_vx=-20.0,
            safe_left_delta=8.0,
            safe_right_delta=60.0,
        ),
        _row(
            step=2,
            action="RIGHT",
            x=101.0,
            next_x=106.0,
            vx=-20.0,
            next_vx=30.0,
            safe_left_delta=-70.0,
            safe_right_delta=-5.0,
        ),
    ]

    analysis = analyze_alignment_records(rows)

    assert analysis["records"] == 3
    assert analysis["cadence_ms"]["median"] == 100.0
    assert analysis["action_response"]["RIGHT"]["delta_vx_median"] == 50.0
    assert analysis["directional_reversal_count"] == 2
    assert analysis["target_conflicting_directional_steps"] == 2


def test_analyze_alignment_records_confirms_rising_support_timeout_alias() -> None:
    rows = [
        _row(
            step=step,
            action="RIGHT" if step < 4 else "LEFT",
            x=100.0 + step,
            next_x=101.0 + step,
            motion="rising",
            support=True,
            departure=True,
            departure_steps=step,
            reason=(
                "support_departure_safety_abort"
                if step == 8
                else "depart_support_platform"
            ),
        )
        for step in range(9)
    ]

    analysis = analyze_alignment_records(rows)

    assert analysis["rising_support_persistence_records"] == 9
    assert analysis["max_rising_support_persistence_streak"] == 9
    assert analysis["support_departure_timeout_count"] == 1
    assert analysis["support_phase_alias_status"] == "SUPPORT_PHASE_ALIAS_CONFIRMED"
    assert analysis["support_departure_direction_reversal_count"] == 1


def test_departure_reversal_does_not_bridge_separate_departures() -> None:
    rows = [
        _row(step=0, action="RIGHT", departure=True),
        _row(step=1, action="RELEASE_ALL", departure=False),
        _row(step=2, action="LEFT", departure=True),
    ]

    analysis = analyze_alignment_records(rows)

    assert analysis["support_departure_direction_reversal_count"] == 0


def test_alignment_gate_fails_when_real_kinds_are_not_in_sim_distribution() -> None:
    primary = []
    for index in range(30):
        step = index % 10
        action = ("LEFT", "RELEASE_ALL", "RIGHT")[index % 3]
        kwargs: dict[str, object] = {}
        if action == "LEFT":
            kwargs.update(next_x=96.0, next_vx=-40.0)
        elif action == "RELEASE_ALL":
            kwargs.update(next_x=100.0, next_vx=0.0)
        primary.append(
            _row(
                step=step,
                episode_id=f"real-{index // 10}",
                action=action,
                target_kind="spring" if index == 0 else "normal",
                **kwargs,
            )
        )
    simulator = [
        _row(
            step=index % 10,
            episode_id=f"sim-{index // 10}",
            action=("LEFT", "RELEASE_ALL", "RIGHT")[index % 3],
            next_vx=(-40.0, 0.0, 40.0)[index % 3],
        )
        for index in range(30)
    ]

    result = evaluate_simulator_real_alignment(
        primary,
        [],
        simulator,
        primary_packet_status="PASS_REAL_ALIGNMENT_PACKET",
        simulator_config=ShaftEnvConfig(
            enable_health=True,
            enable_spikes=True,
            spike_spawn_probability=0.1,
            minimum_normal_platforms_between_spikes=5,
        ),
    )

    assert result["status"] == "FAIL_STOP_SIMULATOR_REAL_ALIGNMENT"
    assert result["gate"]["checks"]["important_kinds_enabled"] is False
    assert result["platform_kinds"]["missing_from_simulator_distribution"] == [
        "spring"
    ]


def test_alignment_gate_reports_insufficient_action_samples() -> None:
    rows = [
        _row(step=step % 10, episode_id=f"ep-{step // 10}")
        for step in range(30)
    ]
    result = evaluate_simulator_real_alignment(
        rows,
        [],
        rows,
        primary_packet_status="PASS_REAL_ALIGNMENT_PACKET",
        simulator_config=ShaftEnvConfig(),
    )

    assert result["status"] == "INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_AUDIT"
    assert result["gate"]["checks"]["action_samples_sufficient"] is False


def test_collect_simulator_alignment_records_is_bounded_and_causal() -> None:
    records = collect_simulator_alignment_records(
        [8123],
        config=ShaftEnvConfig(max_episode_steps=5),
        profile=SIMULATOR_TEACHER_PROFILES["departure_delayed"],
    )

    assert 1 <= len(records) <= 5
    assert [row["step"] for row in records] == list(range(len(records)))
    assert all(
        row["next_observation"]["timestamp"]
        > row["observation"]["timestamp"]
        for row in records
    )
    assert all(row["timing"]["action_duration_ms"] == 100.0 for row in records)
