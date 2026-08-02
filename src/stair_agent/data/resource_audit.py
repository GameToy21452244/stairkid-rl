from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .schema import OBSERVATION_DIM, SCHEMA_VERSION
from .validator import DatasetValidator


AUDIT_FIELDS = (
    "source_file",
    "episode_id",
    "row_count",
    "schema_valid",
    "observation_dim_valid",
    "action_valid",
    "timestamp_valid",
    "terminal_continuity_valid",
    "next_observation_valid",
    "policy_source",
    "environment_source",
    "action_distribution",
    "duplicate_ratio",
    "nan_inf_count",
    "observation_jump_count",
    "usable_for_bc",
    "usable_for_replay",
    "usable_for_dynamics",
    "needs_relabel",
    "rejected",
    "reject_reason",
    "demo_quality",
    "teacher_confidence",
    "verified",
    "classification",
)


@dataclass(frozen=True)
class ResourceAuditRow:
    source_file: str
    episode_id: str
    row_count: int
    schema_valid: bool
    observation_dim_valid: bool
    action_valid: bool
    timestamp_valid: bool
    terminal_continuity_valid: bool
    next_observation_valid: bool
    policy_source: str
    environment_source: str
    action_distribution: str
    duplicate_ratio: float
    nan_inf_count: int
    observation_jump_count: int
    usable_for_bc: bool
    usable_for_replay: bool
    usable_for_dynamics: bool
    needs_relabel: bool
    rejected: bool
    reject_reason: str
    demo_quality: str
    teacher_confidence: float
    verified: bool
    classification: str

    def to_csv_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in tuple(payload.items()):
            if isinstance(value, bool):
                payload[key] = str(value).lower()
        return payload


@dataclass(frozen=True)
class ResourceAuditResult:
    inventory: list[ResourceAuditRow]
    salvage_rows: list[dict[str, Any]]

    @property
    def total_rows(self) -> int:
        return sum(row.row_count for row in self.inventory)


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    return True


def _action_value(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value in {0, 1, 2}:
        return value
    names = {"RELEASE_ALL": 0, "RELEASE": 0, "LEFT": 1, "RIGHT": 2}
    if isinstance(value, str):
        return names.get(value.upper())
    return None


def _feature_dim(payload: dict[str, Any]) -> int | None:
    observation = payload.get("observation")
    if isinstance(observation, list):
        return len(observation)
    features = payload.get("features")
    if isinstance(features, list):
        return len(features)
    return None


def _environment_source(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("calibration_v1"):
        return "real_game_calibration"
    if name.startswith(("baseline_", "reward_audit_", "observations")):
        return "real_game_legacy"
    return "unknown"


def _episode_groups(
    path: Path, records: list[tuple[int, dict[str, Any]]]
) -> list[tuple[str, list[tuple[int, dict[str, Any]]]]]:
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for line_number, payload in records:
        episode = payload.get("episode_id")
        if not isinstance(episode, str) or not episode:
            episode = f"legacy:{path.stem}"
        groups[episode].append((line_number, payload))
    return list(groups.items())


def _audit_group(
    root: Path,
    path: Path,
    episode_id: str,
    records: list[tuple[int, dict[str, Any]]],
) -> tuple[ResourceAuditRow, list[dict[str, Any]]]:
    payloads = [payload for _line, payload in records]
    canonical = all(payload.get("schema_version") == SCHEMA_VERSION for payload in payloads)
    dimensions = [_feature_dim(payload) for payload in payloads]
    observation_dim_valid = bool(dimensions) and all(
        dimension == OBSERVATION_DIM for dimension in dimensions
    )
    actions = [_action_value(payload.get("action")) for payload in payloads]
    action_valid = bool(actions) and all(action is not None for action in actions)
    next_valid = bool(payloads) and all(
        isinstance(payload.get("next_observation"), list)
        and len(payload["next_observation"]) == OBSERVATION_DIM
        for payload in payloads
    )
    timestamp_names = (
        "observation_timestamp",
        "action_command_timestamp",
        "action_effective_timestamp",
        "next_observation_timestamp",
    )
    timestamp_valid = bool(payloads) and all(
        all(isinstance(payload.get(name), (int, float)) for name in timestamp_names)
        and all(
            float(payload[timestamp_names[index]])
            <= float(payload[timestamp_names[index + 1]])
            for index in range(len(timestamp_names) - 1)
        )
        for payload in payloads
    )
    terminal_valid = True
    closed = False
    previous_step: int | None = None
    for payload in payloads:
        step = payload.get("step")
        if closed or (
            previous_step is not None
            and isinstance(step, int)
            and step != previous_step + 1
        ):
            terminal_valid = False
        if isinstance(step, int):
            previous_step = step
        closed = bool(payload.get("terminated") or payload.get("truncated"))
    counts = Counter(action for action in actions if action is not None)
    action_distribution = json.dumps(
        {str(action): counts.get(action, 0) for action in (0, 1, 2)},
        separators=(",", ":"),
    )
    signatures = Counter(
        hashlib.sha256(
            json.dumps(
                [
                    (
                        payload["observation"]
                        if "observation" in payload
                        else payload.get("features", payload)
                    ),
                    payload.get("action"),
                    payload.get("next_observation"),
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for payload in payloads
    )
    duplicates = sum(count - 1 for count in signatures.values() if count > 1)
    duplicate_ratio = duplicates / max(1, len(payloads))
    nan_inf_count = sum(not _finite(payload) for payload in payloads)
    policy_sources = {
        str(payload.get("policy_source", "baseline" if path.name.startswith("baseline_") else "invalid"))
        for payload in payloads
    }
    policy_source = next(iter(policy_sources)) if len(policy_sources) == 1 else "mixed"
    warnings: list[str] = []
    jump_count = 0
    if canonical:
        validation = DatasetValidator().validate_file(path)
        jump_count = sum(issue.code == "observation_jump" for issue in validation.issues)
        if validation.error_count:
            warnings.append("schema_or_continuity_error")
    else:
        for reason, valid in (
            ("missing_or_invalid_schema", canonical),
            ("observation_dimension_invalid", observation_dim_valid),
            ("invalid_or_missing_action", action_valid),
            ("missing_action_timestamps", timestamp_valid),
            ("terminal_continuity_invalid", terminal_valid),
            ("missing_next_observation", next_valid),
        ):
            if not valid:
                warnings.append(reason)

    calibration = _environment_source(path) == "real_game_calibration"
    verified = policy_source in {"human", "baseline_verified", "corrected"}
    usable_for_bc = canonical and verified and not warnings
    usable_for_replay = (
        canonical
        and action_valid
        and next_valid
        and timestamp_valid
        and terminal_valid
        and policy_source != "invalid"
        and not warnings
    )
    usable_for_dynamics = (
        calibration
        and canonical
        and action_valid
        and next_valid
        and timestamp_valid
        and terminal_valid
        and not warnings
    )
    legacy_relabel = (
        _environment_source(path) == "real_game_legacy"
        and path.name.startswith("baseline_")
        and action_valid
        and any(
            isinstance(payload.get("decision_observation"), dict)
            for payload in payloads
        )
    )
    needs_relabel = not usable_for_bc and legacy_relabel
    if usable_for_bc:
        classification = "demo_verified"
    elif usable_for_replay:
        classification = "replay_valid"
    elif needs_relabel:
        classification = "needs_relabel"
    elif usable_for_dynamics:
        classification = "dynamics_only"
    else:
        classification = "invalid"
    rejected = classification == "invalid"
    reject_reason = ";".join(sorted(set(warnings))) if warnings else ""
    if calibration and policy_source == "invalid":
        reject_reason = ";".join(filter(None, (reject_reason, "fixed_calibration_not_expert")))

    row = ResourceAuditRow(
        source_file=str(path.relative_to(root)).replace("\\", "/"),
        episode_id=episode_id,
        row_count=len(payloads),
        schema_valid=canonical and not warnings,
        observation_dim_valid=observation_dim_valid,
        action_valid=action_valid,
        timestamp_valid=timestamp_valid,
        terminal_continuity_valid=terminal_valid,
        next_observation_valid=next_valid,
        policy_source=policy_source,
        environment_source=_environment_source(path),
        action_distribution=action_distribution,
        duplicate_ratio=round(duplicate_ratio, 6),
        nan_inf_count=nan_inf_count,
        observation_jump_count=jump_count,
        usable_for_bc=usable_for_bc,
        usable_for_replay=usable_for_replay,
        usable_for_dynamics=usable_for_dynamics,
        needs_relabel=needs_relabel,
        rejected=rejected,
        reject_reason=reject_reason,
        demo_quality=("verified" if usable_for_bc else "not_expert"),
        teacher_confidence=(1.0 if usable_for_bc else 0.0),
        verified=verified,
        classification=classification,
    )
    salvage_rows = []
    base = row.to_csv_dict()
    for line_number, payload in records:
        salvage_rows.append(
            {
                **base,
                "source_line": line_number,
                "source_step": payload.get("step", ""),
                "row_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }
        )
    return row, salvage_rows


def audit_jsonl_resources(root: str | Path, paths: Iterable[str | Path]) -> ResourceAuditResult:
    root_path = Path(root).resolve()
    inventory: list[ResourceAuditRow] = []
    salvage: list[dict[str, Any]] = []
    for raw_path in sorted((Path(path).resolve() for path in paths), key=str):
        records: list[tuple[int, dict[str, Any]]] = []
        with raw_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"_invalid_json": line.rstrip("\n")}
                if not isinstance(payload, dict):
                    payload = {"_invalid_record": payload}
                records.append((line_number, payload))
        for episode_id, group in _episode_groups(raw_path, records):
            row, row_salvage = _audit_group(root_path, raw_path, episode_id, group)
            inventory.append(row)
            salvage.extend(row_salvage)
    return ResourceAuditResult(inventory=inventory, salvage_rows=salvage)


def write_audit_csvs(
    result: ResourceAuditResult,
    inventory_path: str | Path,
    salvage_path: str | Path,
) -> None:
    inventory_target = Path(inventory_path)
    salvage_target = Path(salvage_path)
    inventory_target.parent.mkdir(parents=True, exist_ok=True)
    salvage_target.parent.mkdir(parents=True, exist_ok=True)
    with inventory_target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(row.to_csv_dict() for row in result.inventory)
    salvage_fields = (*AUDIT_FIELDS, "source_line", "source_step", "row_sha256")
    with salvage_target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=salvage_fields)
        writer.writeheader()
        writer.writerows(result.salvage_rows)


__all__ = [
    "AUDIT_FIELDS",
    "ResourceAuditResult",
    "ResourceAuditRow",
    "audit_jsonl_resources",
    "write_audit_csvs",
]
