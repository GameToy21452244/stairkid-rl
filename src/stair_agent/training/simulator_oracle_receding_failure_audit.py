"""Paired traces for v6 cached versus v7 receding Oracle execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from ..policies.simulator_teachers import OracleFull
from .simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    TARGET_FLOOR,
    edge_fidelity_config,
)


REGRESSION_SEEDS = (
    16011, 16012, 16013, 16019, 16022, 16028, 16029,
    16033, 16034, 16036, 16045, 16054, 16065, 16067,
    16078, 16079, 16081, 16089, 16091, 16093, 16099,
)
RESCUE_SEEDS = (16086,)
BOTH_FAILURE_SEEDS = (16002, 16009, 16030)
CONTROL_SEEDS = (
    16000, 16001, 16003, 16004, 16005,
    16006, 16007, 16008, 16010, 16014,
)


@dataclass(frozen=True)
class OracleTraceStep:
    step: int
    player_x: float
    player_y: float
    velocity_x: float
    velocity_y: float
    deepest_floor_before: int
    supported_floor_before: int | None
    action: str
    planned_now: bool
    planning_count: int
    cached_before: int
    cached_after: int
    plan_actions: tuple[str, ...]
    plan_predicted_floor: int | None
    plan_predicted_terminal: str | None
    plan_score: float | None
    plan_expanded_nodes: int | None
    events: tuple[str, ...]
    deepest_floor_after: int
    terminal_reason: str | None

    @property
    def state_signature(self) -> tuple[object, ...]:
        return (
            self.player_x,
            self.player_y,
            self.velocity_x,
            self.velocity_y,
            self.deepest_floor_before,
            self.supported_floor_before,
        )


@dataclass(frozen=True)
class OracleEpisodeTrace:
    seed: int
    execution: str
    deepest_floor: int
    terminal_reason: str | None
    planning_count: int
    action_horizontal_switches: int
    plan_first_action_horizontal_switches: int
    steps: tuple[OracleTraceStep, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def select_audit_seeds(
    reference_episodes: Iterable[dict[str, object]],
    candidate_episodes: Iterable[dict[str, object]],
) -> dict[str, tuple[int, ...]]:
    reference = {
        int(item["seed"]): int(item["deepest_floor"])
        for item in reference_episodes
    }
    candidate = {
        int(item["seed"]): int(item["deepest_floor"])
        for item in candidate_episodes
    }
    if set(reference) != set(candidate):
        raise ValueError("v6／v7 episode seeds不一致。")
    regression = tuple(sorted(
        seed
        for seed in reference
        if reference[seed] >= TARGET_FLOOR
        and candidate[seed] < TARGET_FLOOR
    ))
    rescue = tuple(sorted(
        seed
        for seed in reference
        if reference[seed] < TARGET_FLOOR
        and candidate[seed] >= TARGET_FLOOR
    ))
    both_failure = tuple(sorted(
        seed
        for seed in reference
        if reference[seed] < TARGET_FLOOR
        and candidate[seed] < TARGET_FLOOR
    ))
    both_success = tuple(sorted(
        seed
        for seed in reference
        if reference[seed] >= TARGET_FLOOR
        and candidate[seed] >= TARGET_FLOOR
    ))
    return {
        "regression": regression,
        "rescue": rescue,
        "both_failure": both_failure,
        "control": both_success[:10],
    }


def horizontal_switches(actions: Iterable[str]) -> int:
    sequence = tuple(actions)
    return sum(
        left in {"LEFT", "RIGHT"}
        and right in {"LEFT", "RIGHT"}
        and left != right
        for left, right in zip(sequence, sequence[1:])
    )


def classify_first_divergence(
    *,
    v6_action: str,
    v7_action: str,
    v6_cached_before: int,
    v7_planned_now: bool,
) -> str:
    if v6_cached_before > 0 and v7_planned_now:
        if (
            v6_action in {"LEFT", "RIGHT"}
            and v7_action in {"LEFT", "RIGHT"}
            and v6_action != v7_action
        ):
            return "cached_vs_replan_opposite"
        if "RELEASE_ALL" in {v6_action, v7_action}:
            return "cached_vs_replan_release"
        return "cached_vs_replan_other"
    return "fallback_or_trigger_divergence"


def run_oracle_trace(seed: int, execution: str) -> OracleEpisodeTrace:
    if execution not in {"cached", "receding"}:
        raise ValueError("execution必須是cached或receding。")
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution=execution,
    )
    env.reset(seed=int(seed))
    trace: list[OracleTraceStep] = []
    terminal_reason: str | None = None
    try:
        for step in range(1, MAX_EPISODE_STEPS + 1):
            simulator = env.simulator
            body = simulator.player.body
            player_x = float(body.position.x)
            player_y = float(body.position.y)
            velocity_x = float(body.velocity.x)
            velocity_y = float(body.velocity.y)
            deepest_floor_before = int(simulator.deepest_floor)
            supported_floor_before = simulator.supported_floor
            cached_before = len(oracle._route_actions)
            planning_before = oracle.route_planning_count
            decision = oracle.choose(simulator)
            planned_now = oracle.route_planning_count > planning_before
            plan = oracle.last_route_plan if planned_now else None
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            if env.simulator.deepest_floor >= TARGET_FLOOR:
                terminal_reason = "target_reached"
            elif terminated or truncated:
                terminal_reason = str(info["terminal_reason"])
            trace.append(OracleTraceStep(
                step=step,
                player_x=player_x,
                player_y=player_y,
                velocity_x=velocity_x,
                velocity_y=velocity_y,
                deepest_floor_before=deepest_floor_before,
                supported_floor_before=supported_floor_before,
                action=decision.action.name,
                planned_now=planned_now,
                planning_count=oracle.route_planning_count,
                cached_before=cached_before,
                cached_after=len(oracle._route_actions),
                plan_actions=(
                    ()
                    if plan is None
                    else tuple(action.name for action in plan.actions)
                ),
                plan_predicted_floor=(
                    None if plan is None else plan.predicted_floor
                ),
                plan_predicted_terminal=(
                    None if plan is None else plan.predicted_terminal
                ),
                plan_score=None if plan is None else plan.score,
                plan_expanded_nodes=(
                    None if plan is None else plan.expanded_nodes
                ),
                events=tuple(str(event) for event in info["events"]),
                deepest_floor_after=int(env.simulator.deepest_floor),
                terminal_reason=terminal_reason,
            ))
            if terminal_reason is not None:
                break
        plan_first_actions = tuple(
            item.plan_actions[0]
            for item in trace
            if item.planned_now and item.plan_actions
        )
        return OracleEpisodeTrace(
            seed=int(seed),
            execution=execution,
            deepest_floor=int(env.simulator.deepest_floor),
            terminal_reason=terminal_reason,
            planning_count=oracle.route_planning_count,
            action_horizontal_switches=horizontal_switches(
                item.action for item in trace
            ),
            plan_first_action_horizontal_switches=horizontal_switches(
                plan_first_actions
            ),
            steps=tuple(trace),
        )
    finally:
        env.close()


def paired_trace_summary(
    v6: OracleEpisodeTrace,
    v7: OracleEpisodeTrace,
) -> dict[str, object]:
    if v6.seed != v7.seed:
        raise ValueError("paired trace seed不一致。")
    divergence = None
    for old, new in zip(v6.steps, v7.steps):
        if old.action != new.action:
            divergence = {
                "step": old.step,
                "states_identical": (
                    old.state_signature == new.state_signature
                ),
                "classification": classify_first_divergence(
                    v6_action=old.action,
                    v7_action=new.action,
                    v6_cached_before=old.cached_before,
                    v7_planned_now=new.planned_now,
                ),
                "v6": asdict(old),
                "v7": asdict(new),
            }
            break
    return {
        "seed": v6.seed,
        "v6": v6.to_dict(),
        "v7": v7.to_dict(),
        "first_divergence": divergence,
        "action_switch_delta_v7_minus_v6": (
            v7.action_horizontal_switches
            - v6.action_horizontal_switches
        ),
        "plan_first_switch_delta_v7_minus_v6": (
            v7.plan_first_action_horizontal_switches
            - v6.plan_first_action_horizontal_switches
        ),
    }


__all__ = [
    "BOTH_FAILURE_SEEDS",
    "CONTROL_SEEDS",
    "REGRESSION_SEEDS",
    "RESCUE_SEEDS",
    "OracleEpisodeTrace",
    "OracleTraceStep",
    "classify_first_divergence",
    "horizontal_switches",
    "paired_trace_summary",
    "run_oracle_trace",
    "select_audit_seeds",
]
