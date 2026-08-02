from __future__ import annotations

from dataclasses import replace

from stair_agent.data.teacher_dataset import (
    TeacherRecord,
    assess_spike_teacher_dataset,
    validate_teacher_records,
)


def record() -> TeacherRecord:
    return TeacherRecord(
        schema_version="ns-shaft-teacher-v1",
        episode_id="e",
        seed=1,
        split="train",
        platform_sequence_id="s",
        step=0,
        observation=[0.0] * 268,
        action=1,
        soft_target=[0.1, 0.8, 0.1],
        teacher_confidence=0.8,
        candidate_action_values=[-2.0, -0.2, -2.0],
        teacher_type="teacher_observable",
        verified=True,
        target_platform_id=1,
        target_platform_kind="normal",
        next_observation=[0.0] * 268,
        reward=1.0,
        events=[],
        terminated=False,
        truncated=False,
        environment_version="ns-shaft-sim-v0.2",
        observation_schema_version="stair-observation-v3-268",
        failure_reason=None,
    )


def test_teacher_schema_accepts_observable_soft_target() -> None:
    assert validate_teacher_records([record()]) == []
    enriched = replace(
        record(),
        visible_platform_kinds=["normal", "spikes"],
        health_segments=7,
        teacher_policy_version="teacher-observable-safe-platform-v2",
        teacher_reason="move_toward_recovery_platform",
    )
    assert validate_teacher_records([enriched]) == []


def test_teacher_schema_rejects_oracle_and_sequence_split_leak() -> None:
    first = record()
    second = replace(
        first,
        episode_id="e2",
        step=0,
        split="test",
        teacher_type="oracle_full",
    )
    issues = validate_teacher_records([first, second])
    assert any("sequence_split_leak" in issue for issue in issues)
    assert any("privileged_teacher" in issue for issue in issues)


def test_teacher_schema_rejects_negative_health_context() -> None:
    issues = validate_teacher_records(
        [replace(record(), health_segments=-1)]
    )
    assert any("health_segments" in issue for issue in issues)


def test_teacher_schema_rejects_blank_policy_provenance() -> None:
    issues = validate_teacher_records(
        [replace(record(), teacher_policy_version="")]
    )
    assert any("teacher_policy_version" in issue for issue in issues)


def test_spike_teacher_dataset_gate_requires_safety_and_coverage() -> None:
    summary = {
        "validator_errors": 0,
        "episodes": 60,
        "action_counts": {"0": 300, "1": 200, "2": 200},
        "split_records": {
            "train": 500,
            "validation": 100,
            "test": 100,
        },
        "spike_visible_records_by_split": {
            "train": 100,
            "validation": 20,
            "test": 20,
        },
        "episodes_with_spike_visible": 35,
        "target_kind_counts": {"spikes": 8, "normal": 500},
        "event_counts": {"damage": 12},
        "terminal_reasons": {"health_depleted": 0},
        "teacher_reason_counts": {
            "move_toward_recovery_platform": 30,
        },
        "all_teacher_verified": True,
        "teacher_policy_version": (
            "teacher-observable-safe-platform-v2"
        ),
    }

    passed = assess_spike_teacher_dataset(summary, expected_episodes=60)
    failed = assess_spike_teacher_dataset(
        {
            **summary,
            "target_kind_counts": {"spikes": 0, "normal": 500},
        },
        expected_episodes=60,
    )

    assert passed["passed"]
    assert all(passed["checks"].values())
    assert not failed["passed"]
    assert not failed["checks"]["spike_target_coverage"]
