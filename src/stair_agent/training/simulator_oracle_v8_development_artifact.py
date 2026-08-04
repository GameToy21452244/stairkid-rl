"""Development-only diagnostics for the frozen Oracle v8 Gate.

This module never defines or imports the v8 holdout partition.  It wraps the
frozen Oracle implementations and records paired v6/v8 development evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import math
from typing import Iterable

import numpy as np

from ..envs.shaft_env import ShaftEnv
from ..policies.simulator_teachers import OracleFull
from .simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    TARGET_FLOOR,
    edge_fidelity_config,
)


DEVELOPMENT_SEEDS = tuple(range(16000, 16100))
SWITCH_RATE_RELATIVE_LIMIT = 1.05


def validate_development_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(int(seed) for seed in seeds)
    if normalized != DEVELOPMENT_SEEDS:
        raise ValueError(
            "Oracle v8 development seeds必須精確為16000～16099。"
        )
    return normalized


def floor_distribution_metrics(
    floors: Iterable[int],
) -> dict[str, float]:
    values = np.asarray(tuple(int(value) for value in floors), dtype=np.float64)
    if values.size == 0:
        raise ValueError("floors不可為空。")
    tail_count = max(1, math.ceil(values.size * 0.25))
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "q25": float(np.quantile(values, 0.25)),
        "cvar25": float(np.mean(np.sort(values)[:tail_count])),
    }


def action_sequence_metrics(actions: Iterable[str]) -> dict[str, object]:
    normalized = tuple(str(action) for action in actions)
    allowed = {"RELEASE_ALL", "LEFT", "RIGHT"}
    if any(action not in allowed for action in normalized):
        raise ValueError("動作序列含有未知動作。")
    counts = Counter(normalized)
    switches = sum(
        left != right for left, right in zip(normalized, normalized[1:])
    )
    direct_reversals = 0
    bridged_reversals = 0
    previous_direction: str | None = None
    releases_since_direction = 0
    for action in normalized:
        if action == "RELEASE_ALL":
            if previous_direction is not None:
                releases_since_direction += 1
            continue
        if previous_direction is not None and action != previous_direction:
            if releases_since_direction:
                bridged_reversals += 1
            else:
                direct_reversals += 1
        previous_direction = action
        releases_since_direction = 0
    total = len(normalized)
    return {
        "steps": total,
        "action_counts": {
            name: int(counts.get(name, 0))
            for name in ("RELEASE_ALL", "LEFT", "RIGHT")
        },
        "release_share": (
            float(counts.get("RELEASE_ALL", 0) / total) if total else 0.0
        ),
        "action_switch_count": int(switches),
        "direct_left_right_reversals": int(direct_reversals),
        "release_bridged_reversals": int(bridged_reversals),
    }


def paired_outcome_metrics(
    reference_rows: Iterable[dict[str, object]],
    candidate_rows: Iterable[dict[str, object]],
) -> dict[str, int]:
    old_rows = tuple(reference_rows)
    new_rows = tuple(candidate_rows)
    reference = {int(row["seed"]): row for row in old_rows}
    candidate = {int(row["seed"]): row for row in new_rows}
    if (
        len(reference) != len(old_rows)
        or len(candidate) != len(new_rows)
        or set(reference) != set(candidate)
    ):
        raise ValueError("v6／v8 paired rows的seeds不一致或重複。")
    outcomes = Counter()
    for seed, old in reference.items():
        old_success = int(old["deepest_floor"]) >= TARGET_FLOOR
        new_success = int(candidate[seed]["deepest_floor"]) >= TARGET_FLOOR
        if old_success and new_success:
            outcomes["both_success"] += 1
        elif old_success:
            outcomes["v6_only_success"] += 1
        elif new_success:
            outcomes["v8_only_success"] += 1
        else:
            outcomes["both_failure"] += 1
    return {
        name: int(outcomes.get(name, 0))
        for name in (
            "both_success",
            "v6_only_success",
            "v8_only_success",
            "both_failure",
        )
    }


def switch_inflation_checks(
    *,
    v6_switches: int,
    v6_steps: int,
    v8_switches: int,
    v8_steps: int,
    non_terminal_paths_identical: bool,
) -> dict[str, bool]:
    v6_rate = 100.0 * int(v6_switches) / max(1, int(v6_steps))
    v8_rate = 100.0 * int(v8_switches) / max(1, int(v8_steps))
    return {
        "non_terminal_paths_identical_to_v6": bool(
            non_terminal_paths_identical
        ),
        "action_switch_rate_inflation_at_most_5_percent": (
            v8_rate <= v6_rate * SWITCH_RATE_RELATIVE_LIMIT + 1e-12
        ),
    }


@dataclass(frozen=True)
class DevelopmentTraceStep:
    step: int
    state_signature: tuple[float | int | None, ...]
    action: str
    cached_before: int
    planned_now: bool
    terminal_risk_before: bool
    plan_predicted_terminal: str | None
    plan_expanded_nodes: int | None


@dataclass(frozen=True)
class DevelopmentEpisode:
    seed: int
    execution: str
    deepest_floor: int
    terminal_reason: str | None
    action_metrics: dict[str, object]
    action_sequence_sha256: str
    route_planning_count: int
    terminal_risk_replan_count: int
    terminal_plan_count: int
    all_plans_within_bounds: bool
    steps: tuple[DevelopmentTraceStep, ...]

    def result_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "execution": self.execution,
            "deepest_floor": self.deepest_floor,
            "terminal_reason": self.terminal_reason,
            **self.action_metrics,
            "action_sequence_sha256": self.action_sequence_sha256,
            "route_planning_count": self.route_planning_count,
            "terminal_risk_replan_count": self.terminal_risk_replan_count,
            "terminal_plan_exposed": self.terminal_plan_count > 0,
            "terminal_plan_count": self.terminal_plan_count,
            "all_plans_within_bounds": self.all_plans_within_bounds,
        }


def run_development_episode(
    seed: int,
    execution: str,
) -> DevelopmentEpisode:
    if int(seed) not in DEVELOPMENT_SEEDS:
        raise ValueError("development trace只允許16000～16099。")
    if execution not in {"cached", "terminal_guarded"}:
        raise ValueError("execution只允許cached或terminal_guarded。")
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution=execution,
    )
    env.reset(seed=int(seed))
    actions: list[str] = []
    trace: list[DevelopmentTraceStep] = []
    terminal_reason: str | None = None
    terminal_risk_replans = 0
    terminal_plan_count = 0
    all_plans_within_bounds = True
    try:
        for step in range(1, MAX_EPISODE_STEPS + 1):
            simulator = env.simulator
            body = simulator.player.body
            state_signature = (
                float(body.position.x),
                float(body.position.y),
                float(body.velocity.x),
                float(body.velocity.y),
                int(simulator.deepest_floor),
                simulator.supported_floor,
            )
            cached_before = len(oracle._route_actions)
            terminal_risk_before = bool(oracle._route_terminal_risk)
            planning_before = oracle.route_planning_count
            decision = oracle.choose(simulator)
            planned_now = oracle.route_planning_count > planning_before
            plan = oracle.last_route_plan if planned_now else None
            if planned_now and terminal_risk_before:
                terminal_risk_replans += 1
            if plan is not None and plan.predicted_terminal is not None:
                terminal_plan_count += 1
            if (
                plan is not None
                and plan.expanded_nodes > 3 * plan.horizon * plan.beam_width
            ):
                all_plans_within_bounds = False
            action_name = decision.action.name
            actions.append(action_name)
            trace.append(DevelopmentTraceStep(
                step=step,
                state_signature=state_signature,
                action=action_name,
                cached_before=cached_before,
                planned_now=planned_now,
                terminal_risk_before=terminal_risk_before,
                plan_predicted_terminal=(
                    None if plan is None else plan.predicted_terminal
                ),
                plan_expanded_nodes=(
                    None if plan is None else plan.expanded_nodes
                ),
            ))
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            if env.simulator.deepest_floor >= TARGET_FLOOR:
                terminal_reason = "target_reached"
            elif terminated or truncated:
                terminal_reason = str(info["terminal_reason"])
            if terminal_reason is not None:
                break
        encoded = "\n".join(actions).encode("utf-8")
        return DevelopmentEpisode(
            seed=int(seed),
            execution=execution,
            deepest_floor=int(env.simulator.deepest_floor),
            terminal_reason=terminal_reason,
            action_metrics=action_sequence_metrics(actions),
            action_sequence_sha256=hashlib.sha256(encoded).hexdigest(),
            route_planning_count=oracle.route_planning_count,
            terminal_risk_replan_count=terminal_risk_replans,
            terminal_plan_count=terminal_plan_count,
            all_plans_within_bounds=all_plans_within_bounds,
            steps=tuple(trace),
        )
    finally:
        env.close()


def paired_episode_diagnostics(
    reference: DevelopmentEpisode,
    candidate: DevelopmentEpisode,
) -> dict[str, object]:
    if reference.seed != candidate.seed:
        raise ValueError("paired episode seed不一致。")
    first_divergence: dict[str, object] | None = None
    for old, new in zip(reference.steps, candidate.steps):
        if old.action == new.action:
            continue
        states_identical = old.state_signature == new.state_signature
        if states_identical and new.terminal_risk_before and new.planned_now:
            classification = "terminal_risk_replan_vs_v6_cached_suffix"
        elif states_identical and new.planned_now:
            classification = "v8_plan_vs_v6_action"
        elif not states_identical:
            classification = "downstream_state_divergence"
        else:
            classification = "fallback_or_cache_divergence"
        first_divergence = {
            "step": old.step,
            "states_identical": states_identical,
            "classification": classification,
            "v6_action": old.action,
            "v8_action": new.action,
            "v6_cached_before": old.cached_before,
            "v8_planned_now": new.planned_now,
            "v8_terminal_risk_before": new.terminal_risk_before,
            "v8_plan_predicted_terminal": new.plan_predicted_terminal,
        }
        break
    if first_divergence is None and len(reference.steps) != len(candidate.steps):
        first_divergence = {
            "step": min(len(reference.steps), len(candidate.steps)) + 1,
            "states_identical": False,
            "classification": "trajectory_length_divergence",
        }
    old_success = reference.deepest_floor >= TARGET_FLOOR
    new_success = candidate.deepest_floor >= TARGET_FLOOR
    outcome = (
        "both_success"
        if old_success and new_success
        else "v6_only_success"
        if old_success
        else "v8_only_success"
        if new_success
        else "both_failure"
    )
    return {
        "seed": reference.seed,
        "outcome": outcome,
        "v6": reference.result_dict(),
        "v8": candidate.result_dict(),
        "first_divergence": first_divergence,
        "action_switch_delta_v8_minus_v6": (
            int(candidate.action_metrics["action_switch_count"])
            - int(reference.action_metrics["action_switch_count"])
        ),
        "direct_reversal_delta_v8_minus_v6": (
            int(candidate.action_metrics["direct_left_right_reversals"])
            - int(reference.action_metrics["direct_left_right_reversals"])
        ),
        "release_bridged_reversal_delta_v8_minus_v6": (
            int(candidate.action_metrics["release_bridged_reversals"])
            - int(reference.action_metrics["release_bridged_reversals"])
        ),
        "non_terminal_reference_path": reference.terminal_plan_count == 0,
        "action_sequence_identical": (
            reference.action_sequence_sha256
            == candidate.action_sequence_sha256
        ),
    }


def aggregate_episode_metrics(
    episodes: Iterable[DevelopmentEpisode],
) -> dict[str, object]:
    rows = tuple(episodes)
    if not rows:
        raise ValueError("episodes不可為空。")
    distribution = floor_distribution_metrics(
        item.deepest_floor for item in rows
    )
    total_actions: Counter[str] = Counter()
    terminals: Counter[str] = Counter()
    for item in rows:
        total_actions.update(item.action_metrics["action_counts"])
        terminals[str(item.terminal_reason)] += 1
    total_steps = sum(int(item.action_metrics["steps"]) for item in rows)
    switches = sum(
        int(item.action_metrics["action_switch_count"]) for item in rows
    )
    return {
        **distribution,
        "episodes": len(rows),
        "reach_floor_3_rate": float(np.mean([
            item.deepest_floor >= 3 for item in rows
        ])),
        "reach_floor_10_rate": float(np.mean([
            item.deepest_floor >= TARGET_FLOOR for item in rows
        ])),
        "bottom_deaths": int(terminals.get("bottom", 0)),
        "top_deaths": int(terminals.get("top", 0)),
        "health_deaths": int(terminals.get("health_depleted", 0)),
        "terminal_reasons": dict(terminals),
        "steps": total_steps,
        "action_counts": {
            name: int(total_actions.get(name, 0))
            for name in ("RELEASE_ALL", "LEFT", "RIGHT")
        },
        "release_share": float(
            total_actions.get("RELEASE_ALL", 0) / max(1, total_steps)
        ),
        "action_switch_count": switches,
        "action_switches_per_100_steps": float(
            100.0 * switches / max(1, total_steps)
        ),
        "direct_left_right_reversals": sum(
            int(item.action_metrics["direct_left_right_reversals"])
            for item in rows
        ),
        "release_bridged_reversals": sum(
            int(item.action_metrics["release_bridged_reversals"])
            for item in rows
        ),
        "route_planning_count": sum(
            item.route_planning_count for item in rows
        ),
        "terminal_risk_replan_count": sum(
            item.terminal_risk_replan_count for item in rows
        ),
        "terminal_plan_exposed_episodes": sum(
            item.terminal_plan_count > 0 for item in rows
        ),
        "terminal_plan_count": sum(item.terminal_plan_count for item in rows),
        "all_plans_within_bounds": all(
            item.all_plans_within_bounds for item in rows
        ),
    }


def result_reproduces_formal(
    episode: DevelopmentEpisode,
    formal: dict[str, object],
) -> bool:
    return (
        episode.seed == int(formal["seed"])
        and episode.deepest_floor == int(formal["deepest_floor"])
        and episode.terminal_reason == formal.get("terminal_reason")
        and int(episode.action_metrics["steps"]) == int(formal["steps"])
        and episode.action_metrics["action_counts"] == formal["action_counts"]
    )


__all__ = [
    "DEVELOPMENT_SEEDS",
    "SWITCH_RATE_RELATIVE_LIMIT",
    "DevelopmentEpisode",
    "DevelopmentTraceStep",
    "action_sequence_metrics",
    "aggregate_episode_metrics",
    "floor_distribution_metrics",
    "paired_episode_diagnostics",
    "paired_outcome_metrics",
    "result_reproduces_formal",
    "run_development_episode",
    "switch_inflation_checks",
    "validate_development_seeds",
]
