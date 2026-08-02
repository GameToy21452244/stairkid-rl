from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np

from .calibration_analysis import player_state


ACTION_NAMES = {0: "RELEASE", 1: "LEFT", 2: "RIGHT"}
SPECIAL_KINDS = {"spring", "spike", "spikes"}
EXCLUDED_PHASE_TOKENS = ("special", "recovery", "wall", "top_pressure")


@dataclass(frozen=True)
class NormalTransition:
    source: str
    step: int
    action: int
    previous_action: int | None
    regime: str
    x: float
    vx: float
    next_x: float
    next_vx: float
    dt: float
    observation_to_next_ms: float
    effective_to_next_ms: float
    processing_to_command_ms: float


@dataclass(frozen=True)
class HorizontalActionModel:
    vx_coefficients: dict[int, np.ndarray]
    dx_coefficients: dict[int, np.ndarray]

    def predicts(self, action: int) -> bool:
        return action in self.vx_coefficients and action in self.dx_coefficients

    def step(
        self,
        *,
        x: float,
        vx: float,
        action: int,
        dt: float,
    ) -> tuple[float, float]:
        vx_coefficients = self.vx_coefficients[action]
        next_vx = float(vx_coefficients @ np.asarray([vx, 1.0]))
        dx_coefficients = self.dx_coefficients[action]
        dx = float(
            dx_coefficients
            @ np.asarray([vx * dt, next_vx * dt, dt], dtype=np.float64)
        )
        return x + dx, next_vx


def classify_action_regime(
    action: int,
    vx: float,
    previous_action: int | None,
    *,
    motion_threshold: float = 20.0,
) -> str:
    if action == 0:
        if previous_action == 1:
            return "first_release_after_left"
        if previous_action == 2:
            return "first_release_after_right"
        if previous_action == 0:
            return "repeated_release"
        return "release_unknown_history"
    if action == 1:
        if vx > motion_threshold:
            return "left_reverse_braking"
        if previous_action == 1:
            return "left_hold"
        if abs(vx) <= motion_threshold:
            return "left_from_low_speed"
        return "left_transition"
    if action == 2:
        if vx < -motion_threshold:
            return "right_reverse_braking"
        if previous_action == 2:
            return "right_hold"
        if abs(vx) <= motion_threshold:
            return "right_from_low_speed"
        return "right_transition"
    return f"unknown_action_{action}"


def select_normal_transition(
    transition: dict[str, Any],
    controller: dict[str, Any] | None,
    *,
    source: str,
    previous_action: int | None,
    confidence_threshold: float = 0.8,
    min_x: float = 72.0,
    max_x: float = 391.0,
) -> NormalTransition | None:
    """Select a conservative real-game row for horizontal dynamics audit.

    The filter intentionally excludes wall, special-platform, recovery, raw
    player-dropout, event, motion-boundary, and screen-edge transitions. It is
    an evidence audit filter and is not used by the live controller.
    """
    if controller is None:
        return None
    memory = controller.get("controller_memory") or {}
    phase = str(memory.get("controller_phase") or "").lower()
    if any(token in phase for token in EXCLUDED_PHASE_TOKENS):
        return None
    if (
        bool(controller.get("wall_guard_active"))
        or bool(controller.get("wall_evacuation_active"))
        or bool(memory.get("wall_guard_active"))
        or bool(memory.get("wall_evacuation_active"))
        or bool(memory.get("special_escape_active"))
        or bool(memory.get("recovery_active"))
    ):
        return None
    if str(controller.get("player_detection_source")) != "raw":
        return None
    if int(controller.get("player_missing_streak", 0) or 0) != 0:
        return None
    if float(controller.get("observation_confidence", 0.0) or 0.0) < confidence_threshold:
        return None
    target_kind = transition.get("target_platform_kind")
    target_kind = target_kind or memory.get("target_platform_kind")
    special_source_kind = memory.get("special_source_platform_kind")
    if str(target_kind).lower() in SPECIAL_KINDS:
        return None
    if str(special_source_kind).lower() in SPECIAL_KINDS:
        return None
    if transition.get("events"):
        return None
    try:
        before = player_state(transition["observation"])
        after = player_state(transition["next_observation"])
        observation_timestamp = float(transition["observation_timestamp"])
        effective_timestamp = float(transition["action_effective_timestamp"])
        command_timestamp = float(transition["action_command_timestamp"])
        next_timestamp = float(transition["next_observation_timestamp"])
        action = int(transition["action"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    dt = next_timestamp - observation_timestamp
    if (
        action not in ACTION_NAMES
        or before["present"] <= 0.5
        or after["present"] <= 0.5
        or not min_x <= before["x"] <= max_x
        or not 0 < dt <= 0.25
        or abs(before["motion"]) <= 0.5
        or before["motion"] != after["motion"]
    ):
        return None
    return NormalTransition(
        source=source,
        step=int(transition.get("step", 0)),
        action=action,
        previous_action=previous_action,
        regime=classify_action_regime(action, before["vx"], previous_action),
        x=float(before["x"]),
        vx=float(before["vx"]),
        next_x=float(after["x"]),
        next_vx=float(after["vx"]),
        dt=dt,
        observation_to_next_ms=dt * 1000.0,
        effective_to_next_ms=(next_timestamp - effective_timestamp) * 1000.0,
        processing_to_command_ms=(command_timestamp - observation_timestamp) * 1000.0,
    )


def fit_horizontal_action_model(
    samples: Iterable[NormalTransition],
    *,
    minimum_action_samples: int = 3,
) -> HorizontalActionModel:
    grouped: dict[int, list[NormalTransition]] = defaultdict(list)
    for sample in samples:
        grouped[sample.action].append(sample)
    vx_coefficients: dict[int, np.ndarray] = {}
    dx_coefficients: dict[int, np.ndarray] = {}
    for action, rows in grouped.items():
        if len(rows) < minimum_action_samples:
            continue
        vx_matrix = np.asarray([[row.vx, 1.0] for row in rows])
        vx_targets = np.asarray([row.next_vx for row in rows])
        vx_fit = np.linalg.lstsq(vx_matrix, vx_targets, rcond=None)[0]
        dx_matrix = []
        dx_targets = []
        for row in rows:
            predicted_vx = float(vx_fit @ np.asarray([row.vx, 1.0]))
            dx_matrix.append(
                [row.vx * row.dt, predicted_vx * row.dt, row.dt]
            )
            dx_targets.append(row.next_x - row.x)
        vx_coefficients[action] = vx_fit
        dx_coefficients[action] = np.linalg.lstsq(
            np.asarray(dx_matrix),
            np.asarray(dx_targets),
            rcond=None,
        )[0]
    return HorizontalActionModel(vx_coefficients, dx_coefficients)


def _mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _summarize_errors(rows: Sequence[dict[str, float]]) -> dict[str, Any]:
    return {
        "samples": len(rows),
        "model_x_mae": _mean([row["model_x"] for row in rows]),
        "carry_x_mae": _mean([row["carry_x"] for row in rows]),
        "model_vx_mae": _mean([row["model_vx"] for row in rows]),
        "carry_vx_mae": _mean([row["carry_vx"] for row in rows]),
    }


def leave_one_episode_out(
    samples: Iterable[NormalTransition],
) -> dict[str, Any]:
    """Episode-held-out horizontal audit using the existing model form."""
    rows = list(samples)
    sources = sorted({row.source for row in rows})
    all_errors: list[dict[str, Any]] = []
    rollout_errors: dict[int, list[dict[str, float]]] = {
        horizon: [] for horizon in range(2, 6)
    }
    for source in sources:
        train = [row for row in rows if row.source != source]
        test = sorted(
            (row for row in rows if row.source == source),
            key=lambda row: row.step,
        )
        model = fit_horizontal_action_model(train)
        for row in test:
            if not model.predicts(row.action):
                continue
            predicted_x, predicted_vx = model.step(
                x=row.x,
                vx=row.vx,
                action=row.action,
                dt=row.dt,
            )
            all_errors.append(
                {
                    "action": row.action,
                    "regime": row.regime,
                    "model_x": abs(predicted_x - row.next_x),
                    "carry_x": abs(row.x + row.vx * row.dt - row.next_x),
                    "model_vx": abs(predicted_vx - row.next_vx),
                    "carry_vx": abs(row.vx - row.next_vx),
                }
            )
        for horizon in range(2, 6):
            for start in range(0, len(test) - horizon + 1):
                window = test[start : start + horizon]
                if any(
                    current.step != previous.step + 1
                    for previous, current in zip(window, window[1:])
                ):
                    continue
                if any(not model.predicts(row.action) for row in window):
                    continue
                predicted_x = window[0].x
                predicted_vx = window[0].vx
                for row in window:
                    predicted_x, predicted_vx = model.step(
                        x=predicted_x,
                        vx=predicted_vx,
                        action=row.action,
                        dt=row.dt,
                    )
                actual_x = window[-1].next_x
                elapsed = sum(row.dt for row in window)
                carry_x = window[0].x + window[0].vx * elapsed
                rollout_errors[horizon].append(
                    {
                        "model_x": abs(predicted_x - actual_x),
                        "carry_x": abs(carry_x - actual_x),
                    }
                )
    by_action = {
        ACTION_NAMES[action]: _summarize_errors(
            [row for row in all_errors if row["action"] == action]
        )
        for action in sorted(ACTION_NAMES)
    }
    regimes = sorted({str(row["regime"]) for row in all_errors})
    by_regime = {
        regime: _summarize_errors(
            [row for row in all_errors if row["regime"] == regime]
        )
        for regime in regimes
    }
    rollouts = {
        str(horizon): {
            "windows": len(errors),
            "model_x_mae": _mean([row["model_x"] for row in errors]),
            "carry_x_mae": _mean([row["carry_x"] for row in errors]),
        }
        for horizon, errors in rollout_errors.items()
    }
    return {
        "episodes": len(sources),
        "overall": _summarize_errors(all_errors),
        "by_action": by_action,
        "by_regime": by_regime,
        "rollouts": rollouts,
    }


def _event_kind(row: dict[str, Any]) -> str | None:
    memory = row.get("controller_memory") or {}
    contact_id = memory.get("special_contact_episode_id")
    kind = str(memory.get("special_source_platform_kind") or "").lower()
    if contact_id is not None and kind in SPECIAL_KINDS:
        return "spikes" if kind == "spike" else kind
    for event in row.get("events") or []:
        event_kind = str(event.get("source_platform_kind") or "").lower()
        if event_kind in SPECIAL_KINDS:
            return "spikes" if event_kind == "spike" else event_kind
    return None


def _floor_value(row: dict[str, Any]) -> int | None:
    floor = row.get("floor") or {}
    value = floor.get("value") if isinstance(floor, dict) else floor
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def aggregate_special_encounters(
    controller_rows: Iterable[dict[str, Any]],
    *,
    source: str,
    max_inactive_gap_steps: int = 5,
    outcome_window_steps: int = 8,
) -> list[dict[str, Any]]:
    """Aggregate contact rows into encounters without trusting physical IDs.

    Rows of the same special kind separated by at most the configured number
    of inactive steps are treated as one diagnostic encounter. This reports
    contact-ID fragmentation; it does not assert that the IDs are one physical
    platform and is not consumed by live control.
    """
    rows = sorted(controller_rows, key=lambda row: int(row.get("step", 0)))
    contacts = [row for row in rows if _event_kind(row) is not None]
    if not contacts:
        return []
    groups: list[list[dict[str, Any]]] = []
    for row in contacts:
        kind = _event_kind(row)
        if not groups:
            groups.append([row])
            continue
        previous = groups[-1][-1]
        inactive_gap = int(row.get("step", 0)) - int(previous.get("step", 0)) - 1
        if _event_kind(previous) == kind and inactive_gap <= max_inactive_gap_steps:
            groups[-1].append(row)
        else:
            groups.append([row])

    by_step = {int(row.get("step", 0)): row for row in rows}
    last_recorded_step = max(by_step, default=-1)
    encounters: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        kind = str(_event_kind(group[0]))
        start = int(group[0].get("step", 0))
        end = int(group[-1].get("step", 0))
        span_rows = [
            by_step[step] for step in range(start, end + 1) if step in by_step
        ]
        outcome_rows = [
            by_step[step]
            for step in range(end + 1, end + outcome_window_steps + 1)
            if step in by_step
        ]
        memory_rows = [row.get("controller_memory") or {} for row in group]
        contact_ids = sorted(
            {
                int(memory["special_contact_episode_id"])
                for memory in memory_rows
                if memory.get("special_contact_episode_id") is not None
            }
        )
        source_ids = sorted(
            {
                int(memory["special_source_platform_id"])
                for memory in memory_rows
                if memory.get("special_source_platform_id") is not None
            }
        )
        all_events = [
            event
            for row in span_rows + outcome_rows
            for event in (row.get("events") or [])
        ]
        directions = [
            str(row.get("action"))
            for row in span_rows
            if str(row.get("action")) in {"LEFT", "RIGHT"}
        ]
        direction_reversals = sum(
            current != previous
            for previous, current in zip(directions, directions[1:])
        )
        start_floor = _floor_value(group[0])
        outcome_floors = [
            value
            for value in (_floor_value(row) for row in outcome_rows)
            if value is not None
        ]
        terminal_event_names = {
            "death",
            "game_over",
            "health_depleted",
            "terminal",
        }
        terminal_within_outcome = any(
            bool(row.get("terminated")) or bool(row.get("truncated"))
            for row in outcome_rows
        ) or any(
            str(event.get("type")) in terminal_event_names
            for event in all_events
        )
        later_same_kind = any(_event_kind(row) == kind for row in outcome_rows)
        normal_landing_count = sum(
            str(event.get("type")) == "landed"
            and str(event.get("source_platform_kind")) == "normal"
            for event in all_events
        )
        encounters.append(
            {
                "source": source,
                "encounter_index": index,
                "kind": kind,
                "start_step": start,
                "end_step": end,
                "span_steps": end - start + 1,
                "contact_steps": len(group),
                "contact_ids": contact_ids,
                "source_platform_ids": source_ids,
                "contact_id_fragmentation": max(0, len(contact_ids) - 1),
                "source_id_fragmentation": max(0, len(source_ids) - 1),
                "bounce_count": sum(
                    str(event.get("type")) == "spring_bounce"
                    for event in all_events
                ),
                "spike_damage_count": sum(
                    str(event.get("type")) == "spike_damage"
                    for event in all_events
                ),
                "health_gain_count": sum(
                    str(event.get("type")) == "health_gained"
                    for event in all_events
                ),
                "normal_landing_count": normal_landing_count,
                "release_count": sum(
                    str(row.get("action")) == "RELEASE_ALL" for row in span_rows
                ),
                "direction_reversal_count": direction_reversals,
                "start_floor": start_floor,
                "max_outcome_floor": max(outcome_floors) if outcome_floors else start_floor,
                "floor_progress": (
                    max(outcome_floors) - start_floor
                    if outcome_floors and start_floor is not None
                    else 0
                ),
                "exit_observed": bool(
                    outcome_rows
                    and not later_same_kind
                    and not terminal_within_outcome
                    and end < last_recorded_step
                ),
                "terminal_within_outcome": terminal_within_outcome,
                "outcome_rows": len(outcome_rows),
            }
        )
    return encounters
