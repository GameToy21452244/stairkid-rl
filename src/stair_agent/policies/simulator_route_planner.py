"""Bounded privileged action-sequence planner for Simulator solvability."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from ..input_controller import Action
from ..simulator.physics import ShaftSimulator, SimulatorSnapshot


@dataclass(frozen=True)
class RoutePlan:
    actions: tuple[Action, ...]
    predicted_floor: int
    predicted_terminal: str | None
    score: float
    expanded_nodes: int
    horizon: int
    beam_width: int


@dataclass(frozen=True)
class _Node:
    snapshot: SimulatorSnapshot
    actions: tuple[Action, ...]
    score: float
    terminal_reason: str | None
    reversals: int


@dataclass(frozen=True)
class FirstActionLane:
    action: Action
    plan: RoutePlan


@dataclass(frozen=True)
class BranchPreservedSearch:
    selected: RoutePlan
    lanes: tuple[FirstActionLane, ...]
    expanded_nodes: int
    runtime_seconds: float
    structural_peak_node_cap: int


class BoundedRoutePlanner:
    """Beam-searches the real simulator step without retaining side effects."""

    BRANCH_EXPANDED_NODE_CAP = 2_379
    BRANCH_STRUCTURAL_PEAK_NODE_CAP = 364
    BRANCH_TIMEOUT_SECONDS = 5.0

    def __init__(self, *, horizon: int = 12, beam_width: int = 24) -> None:
        if horizon < 1:
            raise ValueError("horizon 必須大於 0。")
        if beam_width < 3:
            raise ValueError("beam_width 必須至少為 3。")
        self.horizon = int(horizon)
        self.beam_width = int(beam_width)

    def should_plan(self, simulator: ShaftSimulator) -> bool:
        config = simulator.config
        if not config.enable_calibrated_playfield:
            return False
        player_screen_top = config.height - (
            float(simulator.player.body.position.y)
            + simulator.player.height / 2
        )
        headroom = player_screen_top - config.effective_top_hazard_bottom
        planning_scroll = config.scroll_speed * self.horizon * config.dt
        return headroom <= planning_scroll

    @staticmethod
    def _reversal_count(
        actions: tuple[Action, ...], next_action: Action
    ) -> int:
        if not actions:
            return 0
        previous = actions[-1]
        return int(
            previous in {Action.LEFT, Action.RIGHT}
            and next_action in {Action.LEFT, Action.RIGHT}
            and previous is not next_action
        )

    @staticmethod
    def _alignment_score(
        simulator: ShaftSimulator,
        root_floor: int,
    ) -> float:
        player_x = float(simulator.player.body.position.x)
        half_width = simulator.player.width / 2
        values = []
        for platform in simulator.platforms:
            depth = platform.floor_index - root_floor
            if depth <= 0 or not simulator.platform_is_active(platform):
                continue
            safe_left = platform.left + half_width
            safe_right = platform.right - half_width
            if safe_left <= player_x <= safe_right:
                distance = 0.0
            else:
                distance = min(
                    abs(player_x - safe_left), abs(player_x - safe_right)
                )
            values.append(depth * 45.0 - distance * 1.5)
        return max(values, default=-500.0)

    def _score(
        self,
        simulator: ShaftSimulator,
        *,
        root_floor: int,
        terminal_reason: str | None,
        reversals: int,
        depth: int,
    ) -> float:
        progress = simulator.deepest_floor - root_floor
        player_screen_top = simulator.config.height - (
            float(simulator.player.body.position.y)
            + simulator.player.height / 2
        )
        headroom = (
            player_screen_top
            - simulator.config.effective_top_hazard_bottom
        )
        score = (
            progress * 10_000.0
            + headroom * 5.0
            + self._alignment_score(simulator, root_floor)
            - reversals * 12.0
            - depth * 0.1
        )
        if simulator.supported_floor is None:
            score += 120.0
        if terminal_reason == "top":
            score -= 1_000_000.0
        elif terminal_reason is not None:
            score -= 900_000.0
        return score

    @staticmethod
    def _signature(node: _Node) -> tuple[object, ...]:
        snapshot = node.snapshot
        return (
            round(snapshot.player_position[0] / 6.0),
            round(snapshot.player_position[1] / 6.0),
            round(snapshot.player_velocity[0] / 35.0),
            round(snapshot.player_velocity[1] / 35.0),
            snapshot.supported_floor,
            snapshot.deepest_floor,
            node.actions[-1] if node.actions else None,
        )

    def plan(
        self,
        simulator: ShaftSimulator,
        *,
        forced_first_action: Action | None = None,
    ) -> RoutePlan:
        root = simulator.capture_snapshot()
        root_floor = simulator.deepest_floor
        root_node = _Node(
            snapshot=root,
            actions=(),
            score=self._score(
                simulator,
                root_floor=root_floor,
                terminal_reason=None,
                reversals=0,
                depth=0,
            ),
            terminal_reason=None,
            reversals=0,
        )
        beam = [root_node]
        completed: list[_Node] = []
        expanded_nodes = 0
        try:
            for depth in range(1, self.horizon + 1):
                candidates: list[_Node] = []
                for node in beam:
                    if node.terminal_reason is not None:
                        completed.append(node)
                        continue
                    if node.snapshot.deepest_floor > root_floor:
                        completed.append(node)
                        continue
                    actions = (
                        (forced_first_action,)
                        if depth == 1 and forced_first_action is not None
                        else tuple(Action)
                    )
                    for action in actions:
                        simulator.restore_snapshot(node.snapshot)
                        result = simulator.step(action)
                        expanded_nodes += 1
                        reversals = node.reversals + self._reversal_count(
                            node.actions, action
                        )
                        actions = node.actions + (action,)
                        child = _Node(
                            snapshot=simulator.capture_snapshot(),
                            actions=actions,
                            score=self._score(
                                simulator,
                                root_floor=root_floor,
                                terminal_reason=result.terminal_reason,
                                reversals=reversals,
                                depth=depth,
                            ),
                            terminal_reason=result.terminal_reason,
                            reversals=reversals,
                        )
                        candidates.append(child)
                if not candidates:
                    break
                unique: dict[tuple[object, ...], _Node] = {}
                for node in sorted(
                    candidates, key=lambda item: item.score, reverse=True
                ):
                    unique.setdefault(self._signature(node), node)
                beam = list(unique.values())[: self.beam_width]
            completed.extend(beam)
            best = max(completed, key=lambda item: item.score)
            return RoutePlan(
                actions=best.actions,
                predicted_floor=best.snapshot.deepest_floor,
                predicted_terminal=best.terminal_reason,
                score=best.score,
                expanded_nodes=expanded_nodes,
                horizon=self.horizon,
                beam_width=self.beam_width,
            )
        finally:
            simulator.restore_snapshot(root)

    def plan_first_action_lanes(
        self,
        simulator: ShaftSimulator,
    ) -> BranchPreservedSearch:
        """Search each first action independently, then reuse the selector."""

        root = simulator.capture_snapshot()
        platform_ids = tuple(id(item) for item in simulator.platforms)
        started = perf_counter()
        lanes: list[FirstActionLane] = []
        try:
            for action in Action:
                plan = self.plan(
                    simulator,
                    forced_first_action=action,
                )
                if not plan.actions or plan.actions[0] is not action:
                    raise RuntimeError(
                        f"first-action lane不完整：{action.name}"
                    )
                lanes.append(FirstActionLane(action=action, plan=plan))
                if perf_counter() - started > self.BRANCH_TIMEOUT_SECONDS:
                    raise TimeoutError("branch-preserved search超過5秒。")
            selected = max(lanes, key=lambda item: item.plan.score).plan
            return BranchPreservedSearch(
                selected=selected,
                lanes=tuple(lanes),
                expanded_nodes=sum(item.plan.expanded_nodes for item in lanes),
                runtime_seconds=perf_counter() - started,
                structural_peak_node_cap=(
                    self.BRANCH_STRUCTURAL_PEAK_NODE_CAP
                ),
            )
        finally:
            simulator.restore_snapshot(root)
            if tuple(id(item) for item in simulator.platforms) != platform_ids:
                raise RuntimeError("branch search改變了platform identity。")


__all__ = [
    "BoundedRoutePlanner",
    "BranchPreservedSearch",
    "FirstActionLane",
    "RoutePlan",
]
