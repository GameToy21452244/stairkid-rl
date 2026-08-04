"""Diagnostic real-game alignment packets with causal timing guarantees."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..baseline_policy import PolicyDecision
from ..input_controller import Action
from ..observation import GameObservation
from .writer import ActionTiming


REAL_ALIGNMENT_SCHEMA_VERSION = "real-alignment-packet-v1"
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "diagnostic_only",
    "training_eligible",
    "episode_id",
    "step",
    "decision_frame_index",
    "next_frame_index",
    "observation",
    "next_observation",
    "pre_decision_memory",
    "post_decision_memory",
    "teacher",
    "target_geometry",
    "timing",
    "terminated",
    "truncated",
    "events",
}
_TARGET_FIELDS = {
    "selected",
    "matched",
    "platform_id",
    "kind",
    "signed_offset",
    "center_delta",
    "top_delta",
    "safe_left",
    "safe_right",
    "safe_left_delta",
    "safe_right_delta",
}
_TIMING_FIELDS = {
    "observation_timestamp",
    "action_command_timestamp",
    "action_effective_timestamp",
    "next_observation_timestamp",
    "held_action",
    "action_duration_ms",
}


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_finite_json(value: object, *, path: str = "record") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if _is_number(value):
        if not math.isfinite(float(value)):
            raise ValueError(f"{path}含非有限數值。")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_finite_json(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}含非字串key。")
            _require_finite_json(item, path=f"{path}.{key}")
        return
    raise ValueError(f"{path}含不可序列化型別：{type(value).__name__}。")


def _visible_target_geometry(
    observation: GameObservation,
    decision: PolicyDecision,
    *,
    landing_margin_pixels: float,
) -> dict[str, object]:
    target_id = decision.target_platform_id
    player = observation.player
    player_x = None if player is None else player.get("center_x")
    player_y = None if player is None else player.get("center_y")
    matched_platform = next(
        (
            platform
            for platform in observation.platforms
            if target_id is not None
            and platform.get("track_id") == target_id
        ),
        None,
    )
    empty = {
        "selected": target_id is not None,
        "matched": False,
        "platform_id": target_id,
        "kind": decision.target_platform_kind,
        "signed_offset": decision.horizontal_delta,
        "center_delta": None,
        "top_delta": None,
        "safe_left": None,
        "safe_right": None,
        "safe_left_delta": None,
        "safe_right_delta": None,
    }
    if matched_platform is None or player_x is None or player_y is None:
        return empty
    box = matched_platform.get("box")
    if not isinstance(box, Mapping):
        return empty
    try:
        left = float(box["left"])
        top = float(box["top"])
        width = float(box["width"])
        numeric_player_x = float(player_x)
        numeric_player_y = float(player_y)
    except (KeyError, TypeError, ValueError):
        return empty
    if width < 0.0:
        raise ValueError("target platform width不可為負。")
    margin = min(float(landing_margin_pixels), max(0.0, width / 3.0))
    safe_left = left + margin
    safe_right = left + width - margin
    center_x = left + width / 2.0
    return {
        **empty,
        "matched": True,
        "kind": str(matched_platform.get("kind", decision.target_platform_kind)),
        "center_delta": center_x - numeric_player_x,
        "top_delta": top - numeric_player_y,
        "safe_left": safe_left,
        "safe_right": safe_right,
        "safe_left_delta": safe_left - numeric_player_x,
        "safe_right_delta": safe_right - numeric_player_x,
    }


def build_real_alignment_record(
    *,
    episode_id: str,
    step: int,
    observation: GameObservation,
    next_observation: GameObservation,
    pre_decision_memory: Mapping[str, object],
    post_decision_memory: Mapping[str, object],
    decision: PolicyDecision,
    timing: ActionTiming,
    terminated: bool,
    truncated: bool,
    events: Iterable[Mapping[str, object]],
    landing_margin_pixels: float,
) -> dict[str, object]:
    record = {
        "schema_version": REAL_ALIGNMENT_SCHEMA_VERSION,
        "diagnostic_only": True,
        "training_eligible": False,
        "episode_id": str(episode_id),
        "step": int(step),
        "decision_frame_index": int(step),
        "next_frame_index": int(step) + 1,
        "observation": observation.to_dict(),
        "next_observation": next_observation.to_dict(),
        "pre_decision_memory": dict(pre_decision_memory),
        "post_decision_memory": dict(post_decision_memory),
        "teacher": {
            "action": int(decision.action),
            "action_name": decision.action.name,
            "reason": decision.reason,
            "target_platform_id": decision.target_platform_id,
            "target_platform_kind": decision.target_platform_kind,
            "target_signed_offset": decision.horizontal_delta,
        },
        "target_geometry": _visible_target_geometry(
            observation,
            decision,
            landing_margin_pixels=landing_margin_pixels,
        ),
        "timing": {
            "observation_timestamp": float(observation.timestamp),
            "action_command_timestamp": float(
                timing.action_command_timestamp
            ),
            "action_effective_timestamp": float(
                timing.action_effective_timestamp
            ),
            "next_observation_timestamp": float(
                timing.next_observation_timestamp
            ),
            "held_action": bool(timing.held_action),
            "action_duration_ms": float(timing.action_duration_ms),
        },
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "events": [dict(event) for event in events],
    }
    validate_real_alignment_record(record)
    return record


def validate_real_alignment_record(record: Mapping[str, object]) -> None:
    if not isinstance(record, Mapping):
        raise ValueError("alignment record必須是object。")
    actual = set(record)
    missing = sorted(_TOP_LEVEL_FIELDS - actual)
    unknown = sorted(actual - _TOP_LEVEL_FIELDS)
    if missing or unknown:
        raise ValueError(f"alignment schema欄位不符：missing={missing}, unknown={unknown}")
    if record["schema_version"] != REAL_ALIGNMENT_SCHEMA_VERSION:
        raise ValueError("alignment schema version不符。")
    if record["diagnostic_only"] is not True or record["training_eligible"] is not False:
        raise ValueError("alignment packet只能是diagnostic-only。")
    if not isinstance(record["episode_id"], str) or not record["episode_id"]:
        raise ValueError("episode_id無效。")
    step = record["step"]
    if not isinstance(step, int) or isinstance(step, bool) or step < 0:
        raise ValueError("step無效。")
    if record["decision_frame_index"] != step or record["next_frame_index"] != step + 1:
        raise ValueError("frame index與step未對齊。")
    for key in ("observation", "next_observation", "pre_decision_memory", "post_decision_memory"):
        if not isinstance(record[key], Mapping):
            raise ValueError(f"{key}必須是object。")
    teacher = record["teacher"]
    if not isinstance(teacher, Mapping):
        raise ValueError("teacher必須是object。")
    if teacher.get("action") not in {0, 1, 2}:
        raise ValueError("teacher action無效。")
    expected_name = Action(int(teacher["action"])).name
    if teacher.get("action_name") != expected_name:
        raise ValueError("teacher action name不一致。")
    geometry = record["target_geometry"]
    if not isinstance(geometry, Mapping) or set(geometry) != _TARGET_FIELDS:
        raise ValueError("target geometry欄位不符。")
    selected = geometry["selected"]
    matched = geometry["matched"]
    if not isinstance(selected, bool) or not isinstance(matched, bool):
        raise ValueError("target selected/matched必須是boolean。")
    if matched and not selected:
        raise ValueError("未選target時不得標matched。")
    timing = record["timing"]
    if not isinstance(timing, Mapping) or set(timing) != _TIMING_FIELDS:
        raise ValueError("timing欄位不符。")
    timestamps = [
        timing["observation_timestamp"],
        timing["action_command_timestamp"],
        timing["action_effective_timestamp"],
        timing["next_observation_timestamp"],
    ]
    if not all(_is_number(value) for value in timestamps):
        raise ValueError("timing timestamp必須是數值。")
    numeric_timestamps = [float(value) for value in timestamps]
    observation_timestamp = record["observation"].get("timestamp")
    next_timestamp = record["next_observation"].get("timestamp")
    if not _is_number(observation_timestamp) or not math.isclose(
        float(observation_timestamp), numeric_timestamps[0], abs_tol=1e-6
    ):
        raise ValueError("observation timestamp與timing不一致。")
    if not _is_number(next_timestamp) or not math.isclose(
        float(next_timestamp), numeric_timestamps[-1], abs_tol=1e-6
    ):
        raise ValueError("next observation timestamp與timing不一致。")
    if numeric_timestamps != sorted(numeric_timestamps):
        raise ValueError("action timing順序錯誤。")
    if not isinstance(timing["held_action"], bool):
        raise ValueError("held_action必須是boolean。")
    if not _is_number(timing["action_duration_ms"]) or float(
        timing["action_duration_ms"]
    ) < 0.0:
        raise ValueError("action_duration_ms無效。")
    for name in ("terminated", "truncated"):
        if not isinstance(record[name], bool):
            raise ValueError(f"{name}必須是boolean。")
    if not isinstance(record["events"], list) or not all(
        isinstance(event, Mapping) for event in record["events"]
    ):
        raise ValueError("events必須是object list。")
    _require_finite_json(dict(record))


def _context_tags(record: Mapping[str, object]) -> set[str]:
    teacher = record["teacher"]
    memory = record["post_decision_memory"]
    geometry = record["target_geometry"]
    tags: set[str] = set()
    kinds = {
        teacher.get("target_platform_kind"),
        geometry.get("kind"),
        memory.get("special_source_platform_kind"),
    }
    for observation_key in ("observation", "next_observation"):
        observation = record[observation_key]
        for event in observation.get("events", []):
            kinds.add(event.get("source_platform_kind"))
    if "normal" in kinds:
        tags.add("ordinary")
    if "spring" in kinds:
        tags.add("spring")
    if "spikes" in kinds:
        tags.add("spikes")
    edge = memory.get("support_edge_distance")
    if (
        bool(memory.get("support_contact_active"))
        and _is_number(edge)
        and float(edge) <= 20.0
    ):
        tags.add("edge")
    if bool(memory.get("wall_guard_active")) or bool(
        memory.get("wall_evacuation_active")
    ):
        tags.add("wall")
    return tags


def audit_real_alignment_records(
    records: Iterable[Mapping[str, object]],
    *,
    expected_episodes: int,
    safety_events: Iterable[Mapping[str, object]],
    expected_record_counts: Mapping[str, int] | None = None,
) -> dict[str, object]:
    frozen = [dict(record) for record in records]
    validation_errors: list[str] = []
    valid_records: list[dict[str, object]] = []
    for index, record in enumerate(frozen):
        try:
            validate_real_alignment_record(record)
        except ValueError as exc:
            validation_errors.append(f"record[{index}]: {exc}")
        else:
            valid_records.append(record)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in valid_records:
        episode_id = record.get("episode_id")
        if isinstance(episode_id, str):
            grouped[episode_id].append(record)
    continuity_errors: list[str] = []
    for episode_id, episode_rows in grouped.items():
        ordered = sorted(episode_rows, key=lambda row: int(row.get("step", -1)))
        for index, row in enumerate(ordered):
            if row.get("step") != index:
                continuity_errors.append(f"{episode_id}: step不連續")
                break
            if index == 0:
                memory = row.get("pre_decision_memory", {})
                if (
                    not isinstance(memory, Mapping)
                    or memory.get("controller_phase") != "reset"
                    or memory.get("previous_action") is not None
                ):
                    continuity_errors.append(f"{episode_id}: step0不是reset memory")
            elif row.get("pre_decision_memory") != ordered[index - 1].get(
                "post_decision_memory"
            ):
                continuity_errors.append(f"{episode_id}: pre/post memory不連續")
            if index < len(ordered) - 1 and (
                bool(row.get("terminated")) or bool(row.get("truncated"))
            ):
                continuity_errors.append(f"{episode_id}: terminal後仍有record")
    counts_match = True
    if expected_record_counts is not None:
        observed = Counter(str(record.get("episode_id")) for record in frozen)
        counts_match = all(
            observed.get(episode_id, 0) == expected
            for episode_id, expected in expected_record_counts.items()
        ) and set(observed) == set(expected_record_counts)
    tags = Counter(
        tag
        for record in valid_records
        for tag in _context_tags(record)
    )
    selected = sum(
        bool(row["target_geometry"]["selected"])
        for row in valid_records
    )
    matched = sum(
        bool(row["target_geometry"]["matched"])
        for row in valid_records
    )
    match_rate = 0.0 if selected == 0 else matched / selected
    safety = [dict(event) for event in safety_events]
    integrity_checks = {
        "requested_episodes_complete": len(grouped) == expected_episodes,
        "every_episode_has_records": bool(grouped)
        and all(grouped[episode_id] for episode_id in grouped),
        "schema_and_finite_values_valid": not validation_errors,
        "step_frame_and_memory_continuity": not continuity_errors,
        "safety_events_zero": not safety,
        "packet_transition_controller_counts_match": counts_match,
    }
    coverage_checks = {
        "records_at_least_30": len(frozen) >= 30,
        "ordinary_context_records_at_least_20": tags["ordinary"] >= 20,
        "target_geometry_match_rate_at_least_90_percent": match_rate >= 0.90,
        "edge_context_records_at_least_10": tags["edge"] >= 10,
        "spring_context_records_at_least_3": tags["spring"] >= 3,
        "spike_context_records_at_least_3": tags["spikes"] >= 3,
        "wall_context_records_at_least_3": tags["wall"] >= 3,
    }
    integrity_passed = all(integrity_checks.values())
    coverage_passed = all(coverage_checks.values())
    if not integrity_passed:
        status = "FAIL_STOP_ALIGNMENT_DATA_INTEGRITY"
    elif not coverage_passed:
        status = "INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_COVERAGE"
    else:
        status = "PASS_REAL_ALIGNMENT_PACKET"
    return {
        "schema_version": REAL_ALIGNMENT_SCHEMA_VERSION,
        "status": status,
        "passed": status == "PASS_REAL_ALIGNMENT_PACKET",
        "integrity_passed": integrity_passed,
        "coverage_passed": coverage_passed,
        "integrity_checks": integrity_checks,
        "coverage_checks": coverage_checks,
        "metrics": {
            "records": len(frozen),
            "episodes": len(grouped),
            "selected_target_records": selected,
            "matched_target_geometry_records": matched,
            "target_geometry_match_rate": match_rate,
            "ordinary_context_records": tags["ordinary"],
            "edge_context_records": tags["edge"],
            "spring_context_records": tags["spring"],
            "spike_context_records": tags["spikes"],
            "wall_context_records": tags["wall"],
        },
        "validation_errors": validation_errors,
        "continuity_errors": continuity_errors,
        "safety_events": safety,
        "next_stage": (
            "AUDIT_SIMULATOR_REAL_ALIGNMENT"
            if status == "PASS_REAL_ALIGNMENT_PACKET"
            else "STOP_AND_REVIEW_ALIGNMENT_PACKET"
        ),
    }


class RealAlignmentPacketWriter:
    """Write one immutable, diagnostic-only real alignment episode."""

    def __init__(
        self,
        path: str | Path,
        *,
        episode_id: str,
        landing_margin_pixels: float,
        initial_step: int = 0,
        expected_pre_decision_memory: Mapping[str, object] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"拒絕覆寫既有alignment packet：{self.path}")
        self._file = self.path.open("x", encoding="utf-8")
        self.episode_id = str(episode_id)
        self.landing_margin_pixels = float(landing_margin_pixels)
        self._step = int(initial_step)
        self._expected_pre_memory = (
            None
            if expected_pre_decision_memory is None
            else dict(expected_pre_decision_memory)
        )
        self._finished = False
        self.records = 0

    def write_step(
        self,
        *,
        observation: GameObservation,
        next_observation: GameObservation,
        pre_decision_memory: Mapping[str, object],
        post_decision_memory: Mapping[str, object],
        decision: PolicyDecision,
        timing: ActionTiming,
        terminated: bool,
        truncated: bool,
        events: Iterable[Mapping[str, object]],
    ) -> dict[str, object]:
        if self._finished:
            raise RuntimeError("alignment episode已結束，拒絕再寫。")
        pre = dict(pre_decision_memory)
        if self._step == 0:
            if (
                pre.get("controller_phase") != "reset"
                or pre.get("previous_action") is not None
            ):
                raise ValueError("alignment step0必須使用reset pre-decision memory。")
        elif self._expected_pre_memory is None or pre != self._expected_pre_memory:
            raise ValueError("alignment pre/post memory不連續。")
        record = build_real_alignment_record(
            episode_id=self.episode_id,
            step=self._step,
            observation=observation,
            next_observation=next_observation,
            pre_decision_memory=pre,
            post_decision_memory=post_decision_memory,
            decision=decision,
            timing=timing,
            terminated=terminated,
            truncated=truncated,
            events=events,
            landing_margin_pixels=self.landing_margin_pixels,
        )
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()
        self._expected_pre_memory = dict(post_decision_memory)
        self._step += 1
        self.records += 1
        self._finished = bool(terminated or truncated)
        return record

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "RealAlignmentPacketWriter":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


__all__ = [
    "REAL_ALIGNMENT_SCHEMA_VERSION",
    "RealAlignmentPacketWriter",
    "audit_real_alignment_records",
    "build_real_alignment_record",
    "validate_real_alignment_record",
]
