"""Bounded diagnostics for retired Simulator Oracle holdout failures."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from ..policies.simulator_route_planner import BoundedRoutePlanner, RoutePlan
from ..policies.simulator_teachers import OracleFull
from ..simulator.physics import ShaftSimulator
from .simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    TARGET_FLOOR,
    edge_fidelity_config,
)


RETIRED_FAILURE_EXPECTATIONS = {
    14005: (7, "bottom"),
    14013: (6, "top"),
    14025: (9, "top"),
    14057: (3, "bottom"),
    14060: (7, "top"),
    14061: (9, "bottom"),
    14065: (7, "bottom"),
}

DIAGNOSTIC_MODES = (
    "current_v6",
    "receding_current_trigger",
    "always_receding",
    "extended_always_receding",
)


@dataclass(frozen=True)
class PlanTrace:
    step: int
    root_floor: int
    predicted_floor: int
    predicted_terminal: str | None
    actions: tuple[str, ...]
    expanded_nodes: int
    horizon: int
    beam_width: int


@dataclass(frozen=True)
class DiagnosticEpisode:
    mode: str
    seed: int
    steps: int
    deepest_floor: int
    terminal_reason: str | None
    planning_count: int
    total_expanded_nodes: int
    max_expanded_nodes: int
    planner_state_restored: bool
    plan_traces: tuple[PlanTrace, ...]

    @property
    def reached_target(self) -> bool:
        return self.deepest_floor >= TARGET_FLOOR

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {"reached_target": self.reached_target}


class RecedingRouteOracle:
    """Diagnostic-only Oracle that executes only the first planned action."""

    def __init__(
        self,
        *,
        horizon: int,
        beam_width: int,
        always_plan: bool,
    ) -> None:
        self.base = OracleFull(enable_route_planner=False)
        self.planner = BoundedRoutePlanner(
            horizon=horizon,
            beam_width=beam_width,
        )
        self.always_plan = bool(always_plan)
        self.last_route_plan: RoutePlan | None = None
        self.route_planning_count = 0

    def choose(self, simulator: ShaftSimulator) -> Action:
        # Keep the fallback Oracle's causal support-departure state current even
        # when the diagnostic planner overrides this decision.
        fallback = self.base.choose(simulator).action
        if not self.always_plan and not self.planner.should_plan(simulator):
            self.last_route_plan = None
            return fallback
        plan = self.planner.plan(simulator)
        self.last_route_plan = plan
        self.route_planning_count += 1
        if not plan.actions:
            return fallback
        return plan.actions[0]


def _plan_trace(step: int, root_floor: int, plan: RoutePlan) -> PlanTrace:
    return PlanTrace(
        step=step,
        root_floor=root_floor,
        predicted_floor=plan.predicted_floor,
        predicted_terminal=plan.predicted_terminal,
        actions=tuple(action.name for action in plan.actions),
        expanded_nodes=plan.expanded_nodes,
        horizon=plan.horizon,
        beam_width=plan.beam_width,
    )


def run_diagnostic_episode(
    seed: int,
    mode: str,
    *,
    max_episode_steps: int = MAX_EPISODE_STEPS,
    target_floor: int = TARGET_FLOOR,
) -> DiagnosticEpisode:
    if mode not in DIAGNOSTIC_MODES:
        raise ValueError(f"未知的 diagnostic mode：{mode}")
    if max_episode_steps <= 0 or target_floor <= 0:
        raise ValueError("step 與 target floor 必須大於 0。")

    env = ShaftEnv(config=edge_fidelity_config())
    env.reset(seed=int(seed))
    current = mode == "current_v6"
    if current:
        controller: OracleFull | RecedingRouteOracle = OracleFull(
            enable_route_planner=True
        )
    elif mode == "receding_current_trigger":
        controller = RecedingRouteOracle(
            horizon=12,
            beam_width=24,
            always_plan=False,
        )
    elif mode == "always_receding":
        controller = RecedingRouteOracle(
            horizon=12,
            beam_width=24,
            always_plan=True,
        )
    else:
        controller = RecedingRouteOracle(
            horizon=24,
            beam_width=96,
            always_plan=True,
        )

    traces: list[PlanTrace] = []
    state_restored = True
    terminal_reason: str | None = None
    previous_planning_count = 0
    try:
        for step in range(1, max_episode_steps + 1):
            simulator = env.simulator
            root_floor = int(simulator.deepest_floor)
            before = simulator.capture_snapshot()
            if current:
                action = controller.choose(simulator).action
            else:
                action = controller.choose(simulator)
            state_restored &= simulator.capture_snapshot() == before

            if controller.route_planning_count > previous_planning_count:
                plan = controller.last_route_plan
                if plan is None:
                    raise RuntimeError("planning_count 增加但缺少 route plan。")
                traces.append(_plan_trace(step, root_floor, plan))
                previous_planning_count = controller.route_planning_count

            _, _, terminated, truncated, info = env.step(int(action))
            if env.simulator.deepest_floor >= target_floor:
                terminal_reason = "target_reached"
                break
            if terminated or truncated:
                terminal_reason = str(info["terminal_reason"])
                break
        return DiagnosticEpisode(
            mode=mode,
            seed=int(seed),
            steps=step,
            deepest_floor=int(env.simulator.deepest_floor),
            terminal_reason=terminal_reason,
            planning_count=controller.route_planning_count,
            total_expanded_nodes=sum(item.expanded_nodes for item in traces),
            max_expanded_nodes=max(
                (item.expanded_nodes for item in traces), default=0
            ),
            planner_state_restored=state_restored,
            plan_traces=tuple(traces),
        )
    finally:
        env.close()


def current_failure_phenotype(episode: DiagnosticEpisode) -> str:
    if episode.reached_target:
        return "not_a_failure"
    if not episode.plan_traces and episode.terminal_reason == "bottom":
        return "pre_trigger_bottom"
    last_plan = episode.plan_traces[-1] if episode.plan_traces else None
    if (
        last_plan is not None
        and last_plan.predicted_terminal is not None
        and last_plan.predicted_floor <= last_plan.root_floor
    ):
        return "search_found_no_survival"
    if (
        episode.terminal_reason == "bottom"
        and any(
            plan.predicted_floor > plan.root_floor
            for plan in episode.plan_traces
        )
    ):
        return "post_plan_bottom"
    return "other_current_failure"


def counterfactual_attribution(
    episodes: Iterable[DiagnosticEpisode],
) -> str:
    by_mode = {episode.mode: episode for episode in episodes}
    required = set(DIAGNOSTIC_MODES)
    if set(by_mode) != required:
        missing = sorted(required - set(by_mode))
        raise ValueError(f"diagnostic modes 不完整：{missing}")
    if by_mode["receding_current_trigger"].reached_target:
        return "open_loop_execution"
    if by_mode["always_receding"].reached_target:
        return "late_trigger"
    if by_mode["extended_always_receding"].reached_target:
        return "bounded_search_capacity"
    return "unresolved_bounded_search"


__all__ = [
    "DIAGNOSTIC_MODES",
    "RETIRED_FAILURE_EXPECTATIONS",
    "DiagnosticEpisode",
    "PlanTrace",
    "RecedingRouteOracle",
    "counterfactual_attribution",
    "current_failure_phenotype",
    "run_diagnostic_episode",
]

