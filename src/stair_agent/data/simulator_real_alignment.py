"""Bounded diagnostics for Simulator / real-game behavioral alignment."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from ..baseline_policy import PolicyDecision, SafePlatformPolicy
from ..config import BaselineConfig
from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from ..observation import GameObservation
from ..policies.simulator_teachers import SimulatorTeacherProfile
from ..simulator.state import ShaftEnvConfig


ALIGNMENT_AUDIT_SCHEMA_VERSION = "simulator-real-alignment-audit-v1"
IMPLEMENTED_SIMULATOR_KINDS = {
    "normal",
    "spikes",
    "spring",
    "conveyor",
    "flipping",
}
_DIRECTIONAL = {"LEFT", "RIGHT"}


def load_jsonl_records(paths: Iterable[str | Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for raw_path in paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} 不是JSON object。")
                records.append(value)
    return records


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _summary(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "samples": 0,
            "median": None,
            "p25": None,
            "p75": None,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "samples": len(values),
        "median": round(float(np.median(array)), 6),
        "p25": round(float(np.quantile(array, 0.25)), 6),
        "p75": round(float(np.quantile(array, 0.75)), 6),
    }


def _normalized_kind(value: object) -> str | None:
    if value is None:
        return None
    kind = str(value).strip().lower()
    if not kind or kind in {"none", "launch_platform"}:
        return None
    if kind == "spike":
        return "spikes"
    if kind.startswith("conveyor"):
        return "conveyor"
    return kind


def _important_kinds(record: Mapping[str, object]) -> set[str]:
    values: list[object] = []
    teacher = record.get("teacher")
    if isinstance(teacher, Mapping):
        values.append(teacher.get("target_platform_kind"))
    geometry = record.get("target_geometry")
    if isinstance(geometry, Mapping) and bool(geometry.get("matched")):
        values.append(geometry.get("kind"))
    for memory_name in ("pre_decision_memory", "post_decision_memory"):
        memory = record.get(memory_name)
        if isinstance(memory, Mapping):
            values.append(memory.get("special_source_platform_kind"))
    observation = record.get("observation")
    if isinstance(observation, Mapping):
        events = observation.get("events")
        if isinstance(events, list):
            for event in events:
                if isinstance(event, Mapping):
                    values.append(event.get("source_platform_kind"))
    return {
        normalized
        for value in values
        if (normalized := _normalized_kind(value)) is not None
    }


def _player(record: Mapping[str, object], key: str) -> Mapping[str, object]:
    observation = record.get(key)
    if not isinstance(observation, Mapping):
        return {}
    player = observation.get("player")
    return player if isinstance(player, Mapping) else {}


def _memory(record: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = record.get(key)
    return value if isinstance(value, Mapping) else {}


def _teacher(record: Mapping[str, object]) -> Mapping[str, object]:
    value = record.get("teacher")
    return value if isinstance(value, Mapping) else {}


def _rising_support(record: Mapping[str, object]) -> bool:
    memory = _memory(record, "pre_decision_memory")
    if not bool(memory.get("support_contact_active")):
        return False
    player = _player(record, "observation")
    if player.get("motion") != "rising":
        return False
    observation = record.get("observation")
    nearest = (
        observation.get("nearest_platform")
        if isinstance(observation, Mapping)
        else None
    )
    if not isinstance(nearest, Mapping):
        return False
    return nearest.get("track_id") == memory.get("support_platform_id")


def analyze_alignment_records(
    records: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    frozen = [dict(record) for record in records]
    ordered = sorted(
        frozen,
        key=lambda row: (str(row.get("episode_id", "")), int(row.get("step", -1))),
    )
    episodes = {str(row.get("episode_id", "")) for row in ordered}
    cadences_ms: list[float] = []
    response: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"delta_x": [], "delta_vx": []}
    )
    kind_counts: Counter[str] = Counter()
    motion_counts: Counter[str] = Counter()
    support_motion_counts: Counter[str] = Counter()
    target_conflicts: list[dict[str, object]] = []
    generic_reversals: list[dict[str, object]] = []
    departure_reversals: list[dict[str, object]] = []
    timeouts: list[dict[str, object]] = []
    same_source_restarts: list[dict[str, object]] = []
    rising_support_records = 0
    max_rising_streak = 0
    current_rising_streak: dict[str, int] = defaultdict(int)
    previous_direction: dict[str, tuple[int, str]] = {}
    departure_direction: dict[str, tuple[object, str]] = {}
    timeout_sources: dict[str, object] = {}
    departure_alias_counts: dict[tuple[str, object], int] = defaultdict(int)

    for row in ordered:
        episode_id = str(row.get("episode_id", ""))
        step = int(row.get("step", -1))
        teacher = _teacher(row)
        action = str(teacher.get("action_name", ""))
        observation = row.get("observation")
        next_observation = row.get("next_observation")
        timing = row.get("timing")
        if isinstance(timing, Mapping):
            start = _finite_float(timing.get("observation_timestamp"))
            end = _finite_float(timing.get("next_observation_timestamp"))
            if start is not None and end is not None and end >= start:
                cadences_ms.append((end - start) * 1000.0)

        current_player = _player(row, "observation")
        next_player = _player(row, "next_observation")
        x = _finite_float(current_player.get("center_x"))
        next_x = _finite_float(next_player.get("center_x"))
        vx = _finite_float(current_player.get("velocity_x"))
        next_vx = _finite_float(next_player.get("velocity_x"))
        if action in {"LEFT", "RELEASE_ALL", "RIGHT"}:
            if x is not None and next_x is not None:
                response[action]["delta_x"].append(next_x - x)
            if vx is not None and next_vx is not None:
                response[action]["delta_vx"].append(next_vx - vx)

        motion = str(current_player.get("motion", "unknown"))
        motion_counts[motion] += 1
        pre = _memory(row, "pre_decision_memory")
        post = _memory(row, "post_decision_memory")
        if bool(pre.get("support_contact_active")):
            support_motion_counts[motion] += 1

        for kind in _important_kinds(row):
            kind_counts[kind] += 1

        geometry = row.get("target_geometry")
        if action in _DIRECTIONAL and isinstance(geometry, Mapping):
            safe_left = _finite_float(geometry.get("safe_left_delta"))
            safe_right = _finite_float(geometry.get("safe_right_delta"))
            conflict = (
                action == "LEFT" and safe_left is not None and safe_left > 0.0
            ) or (
                action == "RIGHT"
                and safe_right is not None
                and safe_right < 0.0
            )
            if conflict:
                target_conflicts.append(
                    {"episode_id": episode_id, "step": step, "action": action}
                )

        if action in _DIRECTIONAL:
            previous = previous_direction.get(episode_id)
            if (
                previous is not None
                and previous[1] != action
                and step - previous[0] <= 3
            ):
                generic_reversals.append(
                    {
                        "episode_id": episode_id,
                        "from_step": previous[0],
                        "to_step": step,
                        "from_action": previous[1],
                        "to_action": action,
                    }
                )
            previous_direction[episode_id] = (step, action)

        source_id = (
            pre.get("support_departure_source_id")
            if bool(pre.get("support_departure_active"))
            else post.get("support_departure_source_id")
        )
        if source_id is None:
            departure_direction.pop(episode_id, None)
        if source_id is not None:
            direction = (
                post.get("support_departure_direction")
                or pre.get("support_departure_direction")
            )
            if direction in _DIRECTIONAL:
                previous_departure = departure_direction.get(episode_id)
                if (
                    previous_departure is not None
                    and previous_departure[0] == source_id
                    and previous_departure[1] != direction
                ):
                    departure_reversals.append(
                        {
                            "episode_id": episode_id,
                            "step": step,
                            "source_id": source_id,
                            "from_direction": previous_departure[1],
                            "to_direction": direction,
                        }
                    )
                departure_direction[episode_id] = (source_id, str(direction))

        rising = _rising_support(row)
        if rising:
            rising_support_records += 1
            current_rising_streak[episode_id] += 1
            max_rising_streak = max(
                max_rising_streak, current_rising_streak[episode_id]
            )
            if source_id is not None:
                departure_alias_counts[(episode_id, source_id)] += 1
        else:
            current_rising_streak[episode_id] = 0

        reason = str(teacher.get("reason", ""))
        if reason == "support_departure_safety_abort":
            timeout_source = pre.get("support_departure_source_id")
            pre_steps = int(pre.get("support_departure_steps") or 0)
            alias_records = departure_alias_counts.get(
                (episode_id, timeout_source), 0
            )
            sample = {
                "episode_id": episode_id,
                "step": step,
                "source_id": timeout_source,
                "pre_departure_steps": pre_steps,
                "rising_support_records_in_departure": alias_records,
                "alias_confirmed": (
                    timeout_source is not None
                    and pre_steps > 0
                    and alias_records >= pre_steps
                ),
            }
            timeouts.append(sample)
            timeout_sources[episode_id] = timeout_source
        starts_departure = (
            not bool(pre.get("support_departure_active"))
            and bool(post.get("support_departure_active"))
        )
        if starts_departure and timeout_sources.get(episode_id) == post.get(
            "support_departure_source_id"
        ):
            same_source_restarts.append(
                {
                    "episode_id": episode_id,
                    "step": step,
                    "source_id": post.get("support_departure_source_id"),
                }
            )

    action_response: dict[str, object] = {}
    for action in ("LEFT", "RELEASE_ALL", "RIGHT"):
        delta_x = _summary(response[action]["delta_x"])
        delta_vx = _summary(response[action]["delta_vx"])
        action_response[action] = {
            "samples": min(int(delta_x["samples"]), int(delta_vx["samples"])),
            "delta_x_median": delta_x["median"],
            "delta_x_p25": delta_x["p25"],
            "delta_x_p75": delta_x["p75"],
            "delta_vx_median": delta_vx["median"],
            "delta_vx_p25": delta_vx["p25"],
            "delta_vx_p75": delta_vx["p75"],
        }
    confirmed = any(bool(sample["alias_confirmed"]) for sample in timeouts)
    return {
        "records": len(ordered),
        "episodes": len(episodes),
        "cadence_ms": _summary(cadences_ms),
        "action_response": action_response,
        "important_platform_kind_counts": dict(sorted(kind_counts.items())),
        "important_platform_kinds": sorted(kind_counts),
        "motion_counts": dict(sorted(motion_counts.items())),
        "support_motion_counts": dict(sorted(support_motion_counts.items())),
        "rising_support_persistence_records": rising_support_records,
        "rising_support_persistence_rate": (
            0.0 if not ordered else rising_support_records / len(ordered)
        ),
        "max_rising_support_persistence_streak": max_rising_streak,
        "support_departure_timeout_count": len(timeouts),
        "support_departure_timeouts": timeouts,
        "same_support_restart_count": len(same_source_restarts),
        "same_support_restarts": same_source_restarts,
        "support_phase_alias_status": (
            "SUPPORT_PHASE_ALIAS_CONFIRMED"
            if confirmed
            else (
                "SUPPORT_PHASE_ALIAS_RISK"
                if rising_support_records
                else "NO_SUPPORT_PHASE_ALIAS_OBSERVED"
            )
        ),
        "directional_reversal_count": len(generic_reversals),
        "directional_reversals": generic_reversals,
        "target_conflicting_directional_steps": len(target_conflicts),
        "target_conflict_samples": target_conflicts,
        "support_departure_direction_reversal_count": len(departure_reversals),
        "support_departure_direction_reversals": departure_reversals,
    }


def _configured_distribution_kinds(config: ShaftEnvConfig) -> set[str]:
    # v0.2 generator currently samples only normal and optionally spikes.
    kinds = {"normal"}
    if config.enable_spikes and config.spike_spawn_probability > 0.0:
        kinds.add("spikes")
    return kinds


def _median_metric(analysis: Mapping[str, object], action: str) -> float | None:
    response = analysis.get("action_response")
    if not isinstance(response, Mapping):
        return None
    item = response.get(action)
    if not isinstance(item, Mapping):
        return None
    return _finite_float(item.get("delta_vx_median"))


def _samples_sufficient(analysis: Mapping[str, object]) -> bool:
    response = analysis.get("action_response")
    return isinstance(response, Mapping) and all(
        isinstance(response.get(action), Mapping)
        and int(response[action].get("samples", 0)) >= 10
        for action in ("LEFT", "RELEASE_ALL", "RIGHT")
    )


def _direction_response_correct(analysis: Mapping[str, object]) -> bool:
    left = _median_metric(analysis, "LEFT")
    right = _median_metric(analysis, "RIGHT")
    return left is not None and right is not None and left < 0.0 < right


def evaluate_simulator_real_alignment(
    primary_records: Iterable[Mapping[str, object]],
    secondary_records: Iterable[Mapping[str, object]],
    simulator_records: Iterable[Mapping[str, object]],
    *,
    primary_packet_status: str,
    simulator_config: ShaftEnvConfig,
) -> dict[str, object]:
    primary = analyze_alignment_records(primary_records)
    secondary = analyze_alignment_records(secondary_records)
    simulator = analyze_alignment_records(simulator_records)
    real_cadence = _finite_float(primary["cadence_ms"].get("median"))
    sim_cadence = _finite_float(simulator["cadence_ms"].get("median"))
    cadence_in_range = (
        real_cadence is not None and 70.0 <= real_cadence <= 140.0
    )
    cadence_aligned = (
        cadence_in_range
        and sim_cadence is not None
        and abs(sim_cadence - real_cadence) / real_cadence <= 0.25
    )
    important_kinds = set(primary["important_platform_kinds"])
    enabled_kinds = _configured_distribution_kinds(simulator_config)
    missing_kinds = sorted(important_kinds - enabled_kinds)
    record_integrity = (
        primary_packet_status == "PASS_REAL_ALIGNMENT_PACKET"
        and int(primary["records"]) >= 30
        and int(primary["episodes"]) >= 3
    )
    action_samples_sufficient = _samples_sufficient(primary) and _samples_sufficient(
        simulator
    )
    checks = {
        "primary_packet_passed": (
            primary_packet_status == "PASS_REAL_ALIGNMENT_PACKET"
        ),
        "primary_record_and_episode_minimum": (
            int(primary["records"]) >= 30 and int(primary["episodes"]) >= 3
        ),
        "real_cadence_70_to_140_ms": cadence_in_range,
        "simulator_cadence_within_25_percent": cadence_aligned,
        "action_samples_sufficient": action_samples_sufficient,
        "real_direction_response_correct": _direction_response_correct(primary),
        "simulator_direction_response_correct": _direction_response_correct(
            simulator
        ),
        "important_kinds_enabled": not missing_kinds,
        "support_phase_alias_not_confirmed": (
            primary["support_phase_alias_status"]
            != "SUPPORT_PHASE_ALIAS_CONFIRMED"
        ),
        "primary_support_departure_timeouts_zero": (
            int(primary["support_departure_timeout_count"]) == 0
        ),
        "primary_same_support_restarts_zero": (
            int(primary["same_support_restart_count"]) == 0
        ),
    }
    if not record_integrity:
        status = "FAIL_STOP_ALIGNMENT_AUDIT_INTEGRITY"
    elif not action_samples_sufficient:
        status = "INSUFFICIENT_EVIDENCE_STOP_ALIGNMENT_AUDIT"
    elif all(checks.values()):
        status = "PASS_SIMULATOR_REAL_ALIGNMENT_AUDIT"
    else:
        status = "FAIL_STOP_SIMULATOR_REAL_ALIGNMENT"

    real_left = _median_metric(primary, "LEFT")
    real_right = _median_metric(primary, "RIGHT")
    sim_left = _median_metric(simulator, "LEFT")
    sim_right = _median_metric(simulator, "RIGHT")

    def scale_ratio(sim_value: float | None, real_value: float | None) -> float | None:
        if sim_value is None or real_value is None or real_value == 0.0:
            return None
        return abs(sim_value) / abs(real_value)

    return {
        "schema_version": ALIGNMENT_AUDIT_SCHEMA_VERSION,
        "status": status,
        "passed": status == "PASS_SIMULATOR_REAL_ALIGNMENT_AUDIT",
        "training_started": False,
        "real_game_started": False,
        "gate": {"passed": all(checks.values()), "checks": checks},
        "platform_kinds": {
            "real_important": sorted(important_kinds),
            "simulator_mechanisms_implemented": sorted(
                IMPLEMENTED_SIMULATOR_KINDS
            ),
            "simulator_diagnostic_distribution_enabled": sorted(enabled_kinds),
            "simulator_diagnostic_distribution_observed": simulator[
                "important_platform_kinds"
            ],
            "missing_from_simulator_distribution": missing_kinds,
        },
        "action_response_scale_ratio_simulator_over_real": {
            "LEFT_abs_delta_vx_median": scale_ratio(sim_left, real_left),
            "RIGHT_abs_delta_vx_median": scale_ratio(sim_right, real_right),
        },
        "primary_real": primary,
        "secondary_real": secondary,
        "simulator": simulator,
        "next_stage": (
            "FREEZE_ALIGNMENT_AND_PROCEED_TO_DATASET_GATE"
            if status == "PASS_SIMULATOR_REAL_ALIGNMENT_AUDIT"
            else "STOP_AND_FIX_SIMULATOR_DISTRIBUTION_OR_SUPPORT_PHASE"
        ),
    }


def _target_geometry(
    observation: GameObservation,
    decision: PolicyDecision,
    *,
    landing_margin_pixels: float,
) -> dict[str, object]:
    player = observation.player or {}
    player_x = _finite_float(player.get("center_x"))
    target = next(
        (
            platform
            for platform in observation.platforms
            if decision.target_platform_id is not None
            and platform.get("track_id") == decision.target_platform_id
        ),
        None,
    )
    result: dict[str, object] = {
        "selected": decision.target_platform_id is not None,
        "matched": False,
        "platform_id": decision.target_platform_id,
        "kind": decision.target_platform_kind,
        "safe_left_delta": None,
        "safe_right_delta": None,
    }
    if target is None or player_x is None:
        return result
    box = target.get("box")
    if not isinstance(box, Mapping):
        return result
    left = _finite_float(box.get("left"))
    width = _finite_float(box.get("width"))
    if left is None or width is None or width < 0.0:
        return result
    margin = min(float(landing_margin_pixels), max(0.0, width / 3.0))
    result.update(
        matched=True,
        kind=_normalized_kind(target.get("kind")),
        safe_left_delta=left + margin - player_x,
        safe_right_delta=left + width - margin - player_x,
    )
    return result


def collect_simulator_alignment_records(
    seeds: Iterable[int],
    *,
    config: ShaftEnvConfig,
    profile: SimulatorTeacherProfile,
    baseline_config: BaselineConfig | None = None,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for seed in tuple(int(value) for value in seeds):
        env = ShaftEnv(config=config)
        policy = SafePlatformPolicy(
            baseline_config or BaselineConfig(),
            normal_support_departure_enabled=profile.departure_enabled,
            normal_support_departure_delay_steps=profile.departure_delay_steps,
            support_aware_launch_handoff_enabled=(
                profile.support_aware_launch_handoff_enabled
            ),
        )
        env.reset(seed=seed)
        episode_id = f"sim-alignment-seed-{seed}"
        try:
            for step in range(config.max_episode_steps):
                observation = env.last_observation
                if observation is None:
                    raise RuntimeError("Simulator reset後缺少observation。")
                pre = policy.memory_snapshot()
                decision = policy.choose(observation)
                post = policy.memory_snapshot()
                _, _, terminated, truncated, info = env.step(int(decision.action))
                next_observation = env.last_observation
                if next_observation is None:
                    raise RuntimeError("Simulator step後缺少observation。")
                start = float(observation.timestamp)
                end = float(next_observation.timestamp)
                records.append(
                    {
                        "episode_id": episode_id,
                        "step": step,
                        "observation": observation.to_dict(),
                        "next_observation": next_observation.to_dict(),
                        "pre_decision_memory": pre,
                        "post_decision_memory": post,
                        "teacher": {
                            "action": int(decision.action),
                            "action_name": decision.action.name,
                            "reason": decision.reason,
                            "target_platform_kind": decision.target_platform_kind,
                        },
                        "target_geometry": _target_geometry(
                            observation,
                            decision,
                            landing_margin_pixels=config.safe_landing_margin,
                        ),
                        "timing": {
                            "observation_timestamp": start,
                            "action_command_timestamp": start,
                            "action_effective_timestamp": start,
                            "next_observation_timestamp": end,
                            "held_action": False,
                            "action_duration_ms": config.dt * 1000.0,
                        },
                        "events": list(info.get("events", [])),
                    }
                )
                if env.simulator is None:
                    raise RuntimeError("Simulator step後意外關閉。")
                if (
                    env.simulator.deepest_floor >= 10
                    or terminated
                    or truncated
                ):
                    break
        finally:
            env.close()
    return records


__all__ = [
    "ALIGNMENT_AUDIT_SCHEMA_VERSION",
    "IMPLEMENTED_SIMULATOR_KINDS",
    "analyze_alignment_records",
    "collect_simulator_alignment_records",
    "evaluate_simulator_real_alignment",
    "load_jsonl_records",
]
