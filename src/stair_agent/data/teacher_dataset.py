from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .schema import OBSERVATION_DIM, OBSERVATION_SCHEMA_VERSION


TEACHER_SCHEMA_VERSION = "ns-shaft-teacher-v1"


@dataclass(frozen=True)
class TeacherRecord:
    schema_version: str
    episode_id: str
    seed: int
    split: str
    platform_sequence_id: str
    step: int
    observation: list[float]
    action: int
    soft_target: list[float]
    teacher_confidence: float
    candidate_action_values: list[float]
    teacher_type: str
    verified: bool
    target_platform_id: int | None
    target_platform_kind: str | None
    next_observation: list[float]
    reward: float
    events: list[str]
    terminated: bool
    truncated: bool
    environment_version: str
    observation_schema_version: str
    failure_reason: str | None
    visible_platform_kinds: list[str] = field(default_factory=list)
    health_segments: int | None = None
    teacher_policy_version: str = "legacy-unspecified"
    teacher_reason: str | None = None


def validate_teacher_records(records: Iterable[TeacherRecord]) -> list[str]:
    issues: list[str] = []
    sequence_splits: dict[str, str] = {}
    previous: dict[str, TeacherRecord] = {}
    for index, record in enumerate(records):
        prefix = f"row {index}"
        if record.schema_version != TEACHER_SCHEMA_VERSION:
            issues.append(f"{prefix}: schema_version")
        if record.split not in {"train", "validation", "test"}:
            issues.append(f"{prefix}: split")
        prior_split = sequence_splits.setdefault(record.platform_sequence_id, record.split)
        if prior_split != record.split:
            issues.append(f"{prefix}: sequence_split_leak")
        if len(record.observation) != OBSERVATION_DIM or len(record.next_observation) != OBSERVATION_DIM:
            issues.append(f"{prefix}: observation_dimension")
        if record.action not in {0, 1, 2}:
            issues.append(f"{prefix}: action")
        if len(record.soft_target) != 3 or not math.isclose(sum(record.soft_target), 1.0, abs_tol=1e-6):
            issues.append(f"{prefix}: soft_target")
        if len(record.candidate_action_values) != 3:
            issues.append(f"{prefix}: candidate_action_values")
        if not 0.0 <= record.teacher_confidence <= 1.0:
            issues.append(f"{prefix}: teacher_confidence")
        if record.teacher_type != "teacher_observable":
            issues.append(f"{prefix}: privileged_teacher")
        if not record.teacher_policy_version:
            issues.append(f"{prefix}: teacher_policy_version")
        if record.observation_schema_version != OBSERVATION_SCHEMA_VERSION:
            issues.append(f"{prefix}: observation_schema_version")
        if record.health_segments is not None and record.health_segments < 0:
            issues.append(f"{prefix}: health_segments")
        prior = previous.get(record.episode_id)
        if prior is None and record.step != 0:
            issues.append(f"{prefix}: episode_start")
        if prior is not None:
            if prior.terminated or prior.truncated:
                issues.append(f"{prefix}: after_terminal")
            if record.step != prior.step + 1:
                issues.append(f"{prefix}: step_gap")
        previous[record.episode_id] = record
    return issues


def assess_spike_teacher_dataset(
    summary: dict[str, Any],
    *,
    expected_episodes: int,
) -> dict[str, Any]:
    """Apply pre-registered minimum safety and coverage checks."""

    actions = summary.get("action_counts", {})
    splits = summary.get("split_records", {})
    visible_by_split = summary.get(
        "spike_visible_records_by_split", {}
    )
    target_kinds = summary.get("target_kind_counts", {})
    event_counts = summary.get("event_counts", {})
    terminal_reasons = summary.get("terminal_reasons", {})
    teacher_reasons = summary.get("teacher_reason_counts", {})
    recovery_decisions = sum(
        int(count)
        for reason, count in teacher_reasons.items()
        if "recovery" in str(reason)
    )
    checks = {
        "validator_clean": int(summary.get("validator_errors", -1)) == 0,
        "episode_count": int(summary.get("episodes", -1))
        == expected_episodes,
        "all_splits_present": all(
            int(splits.get(split, 0)) > 0
            for split in ("train", "validation", "test")
        ),
        "action_diversity": all(
            int(actions.get(str(action), 0)) >= expected_episodes
            for action in (0, 1, 2)
        ),
        "spike_visible_all_splits": all(
            int(visible_by_split.get(split, 0)) > 0
            for split in ("train", "validation", "test")
        ),
        "spike_visible_episode_coverage": int(
            summary.get("episodes_with_spike_visible", 0)
        )
        >= expected_episodes // 2,
        "spike_target_coverage": int(target_kinds.get("spikes", 0)) >= 5,
        "spike_damage_coverage": int(event_counts.get("damage", 0)) >= 5,
        "recovery_decision_coverage": recovery_decisions > 0,
        "no_health_death": int(
            terminal_reasons.get("health_depleted", 0)
        )
        == 0,
        "all_teacher_verified": bool(summary.get("all_teacher_verified")),
        "policy_provenance": bool(summary.get("teacher_policy_version")),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "criteria": {
            "expected_episodes": expected_episodes,
            "minimum_records_per_action": expected_episodes,
            "minimum_spike_visible_episodes": expected_episodes // 2,
            "minimum_spike_targets": 5,
            "minimum_damage_events": 5,
            "minimum_recovery_decisions": 1,
            "maximum_health_deaths": 0,
        },
    }


def write_teacher_jsonl(records: Iterable[TeacherRecord], path: str | Path) -> dict[str, Any]:
    rows = list(records)
    issues = validate_teacher_records(rows)
    if issues:
        raise ValueError("teacher dataset validation failed: " + ", ".join(issues[:10]))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        for record in rows:
            stream.write(json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":")) + "\n")
    actions = Counter(record.action for record in rows)
    splits = Counter(record.split for record in rows)
    return {
        "records": len(rows),
        "episodes": len({record.episode_id for record in rows}),
        "action_counts": {str(key): actions.get(key, 0) for key in (0, 1, 2)},
        "split_records": dict(splits),
        "validator_errors": 0,
    }


__all__ = [
    "TEACHER_SCHEMA_VERSION",
    "TeacherRecord",
    "assess_spike_teacher_dataset",
    "validate_teacher_records",
    "write_teacher_jsonl",
]
