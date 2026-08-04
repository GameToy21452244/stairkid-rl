"""Paired development evidence for the branch-preserving Oracle."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from typing import Iterable

import numpy as np

from ..envs.shaft_env import ShaftEnv
from ..policies.simulator_teachers import OracleFull
from .simulator_oracle_branch_preservation_gate import (
    CONDITIONAL_DEVELOPMENT_EXTENSION,
    PRIMARY_DEVELOPMENT_SEEDS,
)
from .simulator_oracle_v8_development_artifact import (
    action_sequence_metrics,
    floor_distribution_metrics,
)
from .simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    TARGET_FLOOR,
    edge_fidelity_config,
)


FORMAL_DEVELOPMENT_SEEDS = (
    PRIMARY_DEVELOPMENT_SEEDS + CONDITIONAL_DEVELOPMENT_EXTENSION
)
DIAGNOSTIC_TEST_SEEDS = frozenset((16000, 16002, 16030))


@dataclass(frozen=True)
class BranchTraceStep:
    step: int
    state_signature: tuple[float | int | None, ...]
    action: str
    planned_now: bool
    branch_planned_now: bool
    cached_before: int


@dataclass(frozen=True)
class BranchEpisode:
    seed: int
    execution: str
    deepest_floor: int
    terminal_reason: str | None
    action_metrics: dict[str, object]
    action_sequence_sha256: str
    route_planning_count: int
    terminal_plan_count: int
    branch_preserved_search_count: int
    selected_lane_counts: dict[str, int]
    branch_expanded_nodes: tuple[int, ...]
    branch_runtime_seconds: tuple[float, ...]
    all_plans_within_bounds: bool
    safety_violations: tuple[str, ...]
    steps: tuple[BranchTraceStep, ...]

    def result_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "execution": self.execution,
            "deepest_floor": self.deepest_floor,
            "terminal_reason": self.terminal_reason,
            **self.action_metrics,
            "action_sequence_sha256": self.action_sequence_sha256,
            "route_planning_count": self.route_planning_count,
            "terminal_plan_exposed": self.terminal_plan_count > 0,
            "terminal_plan_count": self.terminal_plan_count,
            "branch_preserved_search_count": (
                self.branch_preserved_search_count
            ),
            "selected_lane_counts": dict(self.selected_lane_counts),
            "branch_expanded_nodes": list(self.branch_expanded_nodes),
            "branch_runtime_seconds": list(self.branch_runtime_seconds),
            "all_plans_within_bounds": self.all_plans_within_bounds,
            "safety_violations": list(self.safety_violations),
        }


def validate_development_execution_seeds(
    seeds: Iterable[int],
) -> tuple[int, ...]:
    normalized = tuple(int(seed) for seed in seeds)
    allowed = {
        PRIMARY_DEVELOPMENT_SEEDS,
        PRIMARY_DEVELOPMENT_SEEDS + CONDITIONAL_DEVELOPMENT_EXTENSION,
    }
    if normalized not in allowed:
        raise ValueError("development只能使用凍結的18000 primary或18000-18199。")
    return normalized


def _record_edge_events(
    *,
    step: int,
    info: dict[str, object],
    previous_deepest: int,
    current_deepest: int,
    current_source_floor: int | None,
    required_departure_floor: int,
    departed_floor: int | None,
    last_landed_floor: int | None,
) -> tuple[int | None, int, int | None, list[str]]:
    violations: list[str] = []
    departure_records = iter(info["support_departures"])
    for event in info["events"]:
        if event == "landed":
            current_source_floor = last_landed_floor
        elif event == "floor_descended":
            if departed_floor != required_departure_floor:
                violations.append(
                    f"step {step}: floor {current_deepest} without edge "
                    f"departure from {required_departure_floor}"
                )
            if current_deepest <= previous_deepest:
                violations.append(
                    f"step {step}: non-increasing floor_descended"
                )
            required_departure_floor = current_deepest
            departed_floor = None
        elif event == "support_departed":
            record = next(departure_records, None)
            if record is None:
                violations.append(
                    f"step {step}: support_departed without record"
                )
            else:
                source_floor = int(record["source_floor"])
                clearance = float(record["clearance"])
                if clearance < -1e-6:
                    violations.append(
                        f"step {step}: source {source_floor} departure "
                        "clearance is negative"
                    )
                if (
                    current_source_floor is not None
                    and current_source_floor != source_floor
                ):
                    violations.append(
                        f"step {step}: departure source {source_floor} != "
                        f"tracked source {current_source_floor}"
                    )
                departed_floor = source_floor
            current_source_floor = None
    return (
        current_source_floor,
        required_departure_floor,
        departed_floor,
        violations,
    )


def run_branch_episode(
    seed: int,
    execution: str,
    *,
    diagnostic: bool = False,
) -> BranchEpisode:
    normalized_seed = int(seed)
    if diagnostic:
        if normalized_seed not in DIAGNOSTIC_TEST_SEEDS:
            raise ValueError("diagnostic只允許已退休的固定test seeds。")
    elif normalized_seed not in FORMAL_DEVELOPMENT_SEEDS:
        raise ValueError("formal development episode seed不在凍結分區。")
    if execution not in {"cached", "branch_preserved"}:
        raise ValueError("execution只允許cached或branch_preserved。")

    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution=execution,
    )
    env.reset(seed=normalized_seed)
    actions: list[str] = []
    trace: list[BranchTraceStep] = []
    violations: list[str] = []
    required_departure_floor = 0
    departed_floor: int | None = None
    terminal_reason: str | None = None
    terminal_plan_count = 0
    branch_expanded_nodes: list[int] = []
    branch_runtime_seconds: list[float] = []
    all_plans_within_bounds = True
    try:
        for step in range(1, MAX_EPISODE_STEPS + 1):
            simulator = env.simulator
            source = simulator.supported_platform
            source_floor = None if source is None else source.floor_index
            previous_deepest = simulator.deepest_floor
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
            planning_before = oracle.route_planning_count
            branch_before = oracle.branch_preserved_search_count
            decision = oracle.choose(simulator)
            planned_now = oracle.route_planning_count > planning_before
            branch_planned_now = (
                oracle.branch_preserved_search_count > branch_before
            )
            plan = oracle.last_route_plan if planned_now else None
            if planned_now and plan is not None:
                if (
                    plan.expanded_nodes
                    > 3 * plan.horizon * plan.beam_width
                ):
                    all_plans_within_bounds = False
                if plan.predicted_terminal is not None:
                    terminal_plan_count += 1
            if branch_planned_now:
                terminal_plan_count += 1
                branch = oracle.last_branch_search
                if branch is None:
                    all_plans_within_bounds = False
                else:
                    branch_expanded_nodes.append(branch.expanded_nodes)
                    branch_runtime_seconds.append(branch.runtime_seconds)
                    all_plans_within_bounds = (
                        all_plans_within_bounds
                        and branch.expanded_nodes <= 2_379
                        and branch.structural_peak_node_cap <= 364
                        and branch.runtime_seconds <= 5.0
                        and all(
                            item.plan.expanded_nodes <= 793
                            for item in branch.lanes
                        )
                    )
            action_name = decision.action.name
            actions.append(action_name)
            trace.append(BranchTraceStep(
                step=step,
                state_signature=state_signature,
                action=action_name,
                planned_now=planned_now,
                branch_planned_now=branch_planned_now,
                cached_before=cached_before,
            ))
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            (
                _current_source,
                required_departure_floor,
                departed_floor,
                step_violations,
            ) = _record_edge_events(
                step=step,
                info=info,
                previous_deepest=previous_deepest,
                current_deepest=env.simulator.deepest_floor,
                current_source_floor=source_floor,
                required_departure_floor=required_departure_floor,
                departed_floor=departed_floor,
                last_landed_floor=env.simulator.last_landed_floor,
            )
            violations.extend(step_violations)
            if env.simulator.deepest_floor >= TARGET_FLOOR:
                terminal_reason = "target_reached"
                break
            if terminated or truncated:
                terminal_reason = str(info["terminal_reason"])
                break
        encoded = "\n".join(actions).encode("utf-8")
        return BranchEpisode(
            seed=normalized_seed,
            execution=execution,
            deepest_floor=int(env.simulator.deepest_floor),
            terminal_reason=terminal_reason,
            action_metrics=action_sequence_metrics(actions),
            action_sequence_sha256=hashlib.sha256(encoded).hexdigest(),
            route_planning_count=oracle.route_planning_count,
            terminal_plan_count=terminal_plan_count,
            branch_preserved_search_count=(
                oracle.branch_preserved_search_count
            ),
            selected_lane_counts=dict(oracle.branch_selected_lane_counts),
            branch_expanded_nodes=tuple(branch_expanded_nodes),
            branch_runtime_seconds=tuple(branch_runtime_seconds),
            all_plans_within_bounds=all_plans_within_bounds,
            safety_violations=tuple(violations),
            steps=tuple(trace),
        )
    finally:
        env.close()


def paired_branch_diagnostics(
    reference: BranchEpisode,
    candidate: BranchEpisode,
) -> dict[str, object]:
    if reference.seed != candidate.seed:
        raise ValueError("paired episode seeds不一致。")
    first_divergence: dict[str, object] | None = None
    for old, new in zip(reference.steps, candidate.steps):
        if old.action == new.action:
            continue
        first_divergence = {
            "step": old.step,
            "states_identical": old.state_signature == new.state_signature,
            "classification": (
                "branch_preserved_vs_v6_terminal_suffix"
                if new.branch_planned_now
                else "downstream_state_divergence"
            ),
            "v6_action": old.action,
            "candidate_action": new.action,
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
        else "candidate_only_success"
        if new_success
        else "both_failure"
    )
    return {
        "seed": reference.seed,
        "outcome": outcome,
        "v6": reference.result_dict(),
        "candidate": candidate.result_dict(),
        "first_divergence": first_divergence,
        "v6_top_failure_repaired": (
            reference.terminal_reason == "top" and new_success
        ),
        "v6_success_regressed": old_success and not new_success,
        "non_terminal_reference_path": reference.terminal_plan_count == 0,
        "action_sequence_identical": (
            reference.action_sequence_sha256
            == candidate.action_sequence_sha256
        ),
    }


def episode_reproducible(
    first: BranchEpisode,
    second: BranchEpisode,
) -> bool:
    return (
        first.seed == second.seed
        and first.execution == second.execution
        and first.deepest_floor == second.deepest_floor
        and first.terminal_reason == second.terminal_reason
        and first.action_metrics == second.action_metrics
        and first.action_sequence_sha256 == second.action_sequence_sha256
        and first.route_planning_count == second.route_planning_count
        and first.terminal_plan_count == second.terminal_plan_count
        and first.branch_preserved_search_count
        == second.branch_preserved_search_count
        and first.selected_lane_counts == second.selected_lane_counts
        and first.branch_expanded_nodes == second.branch_expanded_nodes
        and first.all_plans_within_bounds == second.all_plans_within_bounds
        and first.safety_violations == second.safety_violations
        and first.steps == second.steps
    )


def aggregate_branch_metrics(
    episodes: Iterable[BranchEpisode],
) -> dict[str, object]:
    rows = tuple(episodes)
    if not rows:
        raise ValueError("episodes不可為空。")
    distribution = floor_distribution_metrics(
        item.deepest_floor for item in rows
    )
    actions: Counter[str] = Counter()
    terminals: Counter[str] = Counter()
    lanes: Counter[str] = Counter()
    expanded: list[int] = []
    runtimes: list[float] = []
    for item in rows:
        actions.update(item.action_metrics["action_counts"])
        terminals[str(item.terminal_reason)] += 1
        lanes.update(item.selected_lane_counts)
        expanded.extend(item.branch_expanded_nodes)
        runtimes.extend(item.branch_runtime_seconds)
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
        "reach_floor_5_rate": float(np.mean([
            item.deepest_floor >= 5 for item in rows
        ])),
        "reach_floor_10_rate": float(np.mean([
            item.deepest_floor >= TARGET_FLOOR for item in rows
        ])),
        "bottom_deaths": int(terminals.get("bottom", 0)),
        "top_deaths": int(terminals.get("top", 0)),
        "health_deaths": int(terminals.get("health_depleted", 0)),
        "terminal_reasons": dict(terminals),
        "safety_violations": sum(
            len(item.safety_violations) for item in rows
        ),
        "steps": total_steps,
        "action_counts": {
            name: int(actions.get(name, 0))
            for name in ("RELEASE_ALL", "LEFT", "RIGHT")
        },
        "release_share": float(
            actions.get("RELEASE_ALL", 0) / max(1, total_steps)
        ),
        "max_action_share": float(
            max(actions.values(), default=0) / max(1, total_steps)
        ),
        "collapsed": (
            max(actions.values(), default=0) / max(1, total_steps) >= 0.98
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
        "terminal_plan_exposed_episodes": sum(
            item.terminal_plan_count > 0 for item in rows
        ),
        "terminal_plan_count": sum(item.terminal_plan_count for item in rows),
        "branch_preserved_search_count": sum(
            item.branch_preserved_search_count for item in rows
        ),
        "selected_lane_distribution": {
            name: int(lanes.get(name, 0))
            for name in ("RELEASE_ALL", "LEFT", "RIGHT")
        },
        "branch_compute": {
            "searches": len(expanded),
            "expanded_nodes_total": sum(expanded),
            "expanded_nodes_mean": (
                float(np.mean(expanded)) if expanded else 0.0
            ),
            "expanded_nodes_max": max(expanded, default=0),
            "runtime_seconds_total": sum(runtimes),
            "runtime_seconds_mean": (
                float(np.mean(runtimes)) if runtimes else 0.0
            ),
            "runtime_seconds_max": max(runtimes, default=0.0),
        },
        "all_plans_within_bounds": all(
            item.all_plans_within_bounds for item in rows
        ),
    }


__all__ = [
    "BranchEpisode",
    "BranchTraceStep",
    "DIAGNOSTIC_TEST_SEEDS",
    "FORMAL_DEVELOPMENT_SEEDS",
    "aggregate_branch_metrics",
    "episode_reproducible",
    "paired_branch_diagnostics",
    "run_branch_episode",
    "validate_development_execution_seeds",
]
