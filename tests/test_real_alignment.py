import json
from pathlib import Path

import pytest

from stair_agent.baseline_policy import PolicyDecision
from stair_agent.data.real_alignment import (
    REAL_ALIGNMENT_SCHEMA_VERSION,
    RealAlignmentPacketWriter,
    audit_real_alignment_records,
    validate_real_alignment_record,
)
from stair_agent.data.writer import ActionTiming
from stair_agent.input_controller import Action
from stair_agent.observation import GameObservation


def _observation(
    timestamp: float,
    *,
    target_kind: str = "normal",
    player_x: float = 100.0,
) -> GameObservation:
    platform = {
        "track_id": 7,
        "kind": target_kind,
        "confidence": 1.0,
        "box": {"left": 120.0, "top": 220.0, "width": 90.0, "height": 12.0},
    }
    return GameObservation(
        timestamp=timestamp,
        phase="playing",
        player={
            "center_x": player_x,
            "center_y": 160.0,
            "velocity_x": 15.0,
            "velocity_y": 20.0,
            "motion": "falling",
            "confidence": 0.99,
            "detection_source": "raw",
            "missing_streak": 0,
        },
        health={"segments": 12, "delta": 0, "event": "unchanged"},
        nearest_platform={**platform, "vertical_gap": 45.0},
        platforms=[platform],
        platform_scroll_velocity_y=0.0,
        events=[],
        floor={"value": 2, "delta": 0, "stable": True, "confidence": 1.0},
    )


def _memory(
    phase: str,
    action: str | None,
    *,
    kind: str = "normal",
    edge: float = 12.0,
    wall: bool = False,
) -> dict[str, object]:
    return {
        "controller_phase": phase,
        "previous_action": action,
        "target_platform_id": None if phase == "reset" else 7,
        "target_platform_kind": None if phase == "reset" else kind,
        "target_lock_age_steps": 0 if phase == "reset" else 1,
        "support_contact_active": phase != "reset",
        "support_edge_distance": None if phase == "reset" else edge,
        "wall_guard_active": wall,
        "wall_evacuation_active": wall,
        "special_source_platform_kind": (
            kind if kind in {"spring", "spikes"} else None
        ),
    }


def _timing(start: float) -> ActionTiming:
    return ActionTiming(
        action_command_timestamp=start + 0.02,
        action_effective_timestamp=start + 0.03,
        next_observation_timestamp=start + 0.12,
        held_action=True,
        action_duration_ms=90.0,
    )


def test_alignment_writer_records_predecision_memory_and_target_geometry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "episode.alignment.jsonl"
    writer = RealAlignmentPacketWriter(
        path,
        episode_id="ep-1",
        landing_margin_pixels=10.0,
    )
    before = _memory("reset", None)
    after = _memory("move", "RIGHT")
    writer.write_step(
        observation=_observation(10.0),
        next_observation=_observation(10.12, player_x=108.0),
        pre_decision_memory=before,
        post_decision_memory=after,
        decision=PolicyDecision(
            Action.RIGHT,
            "move_toward_safe_platform",
            target_platform_id=7,
            target_platform_kind="normal",
            horizontal_delta=30.0,
        ),
        timing=_timing(10.0),
        terminated=False,
        truncated=False,
        events=[],
    )
    writer.close()

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["schema_version"] == REAL_ALIGNMENT_SCHEMA_VERSION
    assert row["diagnostic_only"] is True
    assert row["training_eligible"] is False
    assert row["decision_frame_index"] == 0
    assert row["next_frame_index"] == 1
    assert row["pre_decision_memory"] == before
    assert row["post_decision_memory"] == after
    assert row["target_geometry"]["matched"] is True
    assert row["target_geometry"]["safe_left"] == pytest.approx(130.0)
    assert row["target_geometry"]["safe_right"] == pytest.approx(200.0)
    validate_real_alignment_record(row)


def test_alignment_writer_enforces_causal_memory_chain(tmp_path: Path) -> None:
    path = tmp_path / "episode.alignment.jsonl"
    writer = RealAlignmentPacketWriter(
        path,
        episode_id="ep-1",
        landing_margin_pixels=10.0,
    )
    reset = _memory("reset", None)
    post = _memory("move", "RIGHT")
    kwargs = {
        "decision": PolicyDecision(Action.RIGHT, "move", 7, "normal", 20.0),
        "terminated": False,
        "truncated": False,
        "events": [],
    }
    writer.write_step(
        observation=_observation(1.0),
        next_observation=_observation(1.12),
        pre_decision_memory=reset,
        post_decision_memory=post,
        timing=_timing(1.0),
        **kwargs,
    )

    with pytest.raises(ValueError, match="pre/post memory"):
        writer.write_step(
            observation=_observation(1.12),
            next_observation=_observation(1.24),
            pre_decision_memory=reset,
            post_decision_memory=post,
            timing=_timing(1.12),
            **kwargs,
        )
    writer.close()


def test_alignment_validator_rejects_timestamp_drift(tmp_path: Path) -> None:
    path = tmp_path / "episode.alignment.jsonl"
    writer = RealAlignmentPacketWriter(
        path,
        episode_id="ep-1",
        landing_margin_pixels=10.0,
    )
    writer.write_step(
        observation=_observation(2.0),
        next_observation=_observation(2.12),
        pre_decision_memory=_memory("reset", None),
        post_decision_memory=_memory("move", "RIGHT"),
        decision=PolicyDecision(Action.RIGHT, "move", 7, "normal", 20.0),
        timing=_timing(2.0),
        terminated=False,
        truncated=False,
        events=[],
    )
    writer.close()
    row = json.loads(path.read_text(encoding="utf-8"))
    row["timing"]["observation_timestamp"] = 9.0

    with pytest.raises(ValueError, match="observation timestamp"):
        validate_real_alignment_record(row)


def test_alignment_audit_passes_integrity_then_checks_branch_coverage(
    tmp_path: Path,
) -> None:
    records = []
    for episode in range(3):
        pre = _memory("reset", None)
        for step in range(12):
            kind = "spring" if step == 8 else "spikes" if step == 9 else "normal"
            wall = step == 10
            post = _memory("move", "RIGHT", kind=kind, wall=wall)
            path = tmp_path / f"ep-{episode}-{step}.jsonl"
            writer = RealAlignmentPacketWriter(
                path,
                episode_id=f"ep-{episode}",
                landing_margin_pixels=10.0,
                initial_step=step,
                expected_pre_decision_memory=pre,
            )
            writer.write_step(
                observation=_observation(100.0 + step, target_kind=kind),
                next_observation=_observation(100.12 + step, target_kind=kind),
                pre_decision_memory=pre,
                post_decision_memory=post,
                decision=PolicyDecision(Action.RIGHT, "move", 7, kind, 20.0),
                timing=_timing(100.0 + step),
                terminated=False,
                truncated=False,
                events=[],
            )
            writer.close()
            records.append(json.loads(path.read_text(encoding="utf-8")))
            pre = post

    result = audit_real_alignment_records(
        records,
        expected_episodes=3,
        safety_events=[],
    )

    assert result["integrity_passed"] is True
    assert result["metrics"]["records"] == 36
    assert result["metrics"]["target_geometry_match_rate"] == 1.0
    assert result["metrics"]["spring_context_records"] == 3
    assert result["metrics"]["spike_context_records"] == 3
    assert result["metrics"]["wall_context_records"] == 3
    assert result["status"] == "PASS_REAL_ALIGNMENT_PACKET"


def test_alignment_audit_reports_malformed_record_without_crashing() -> None:
    result = audit_real_alignment_records(
        [{"episode_id": "broken", "step": 0}],
        expected_episodes=3,
        safety_events=[],
    )

    assert result["status"] == "FAIL_STOP_ALIGNMENT_DATA_INTEGRITY"
    assert result["integrity_passed"] is False
    assert result["validation_errors"]
