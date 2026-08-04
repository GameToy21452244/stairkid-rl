"""Offline-only diagnostics for the rejected Oracle v8 development result."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from ..policies.simulator_route_planner import BoundedRoutePlanner
from ..policies.simulator_teachers import OracleFull
from ..simulator.physics import ShaftSimulator, SimulatorSnapshot
from .simulator_v03_edge_gate import MAX_EPISODE_STEPS, edge_fidelity_config


TOP_FAILURE_SEEDS = (16002, 16030)
FORMAL_HORIZON = 12
FORMAL_BEAM_WIDTH = 24
TIMELINE_LOOKBACK_STEPS = 24


@dataclass(frozen=True)
class _DiagnosticNode:
    snapshot: SimulatorSnapshot
    actions: tuple[Action, ...]
    score: float
    terminal_reason: str | None
    reversals: int
    events: tuple[str, ...]
    minimum_headroom: float


def _headroom(
    simulator: ShaftSimulator,
    snapshot: SimulatorSnapshot | None = None,
) -> float:
    position_y = (
        float(simulator.player.body.position.y)
        if snapshot is None
        else float(snapshot.player_position[1])
    )
    player_screen_top = simulator.config.height - (
        position_y + simulator.player.height / 2
    )
    return float(
        player_screen_top
        - simulator.config.effective_top_hazard_bottom
    )


def _node_summary(
    simulator: ShaftSimulator,
    node: _DiagnosticNode,
    *,
    root_floor: int,
    horizon: int,
) -> dict[str, object]:
    terminal_step = (
        len(node.actions) if node.terminal_reason is not None else None
    )
    events = Counter(node.events)
    floor_progress = node.snapshot.deepest_floor - root_floor
    completion_reason = (
        "terminal"
        if node.terminal_reason is not None
        else "floor_progress"
        if floor_progress > 0
        else "horizon"
        if len(node.actions) >= horizon
        else "search_exhausted"
    )
    return {
        "actions": [action.name for action in node.actions],
        "first_action": (
            None if not node.actions else node.actions[0].name
        ),
        "score": float(node.score),
        "predicted_terminal_reason": node.terminal_reason,
        "terminal_step": terminal_step,
        "evaluated_steps": len(node.actions),
        "survival_steps_before_terminal": (
            len(node.actions)
            if terminal_step is None
            else max(0, terminal_step - 1)
        ),
        "survived_to_horizon": (
            node.terminal_reason is None and len(node.actions) >= horizon
        ),
        "nonterminal_or_floor_progress": node.terminal_reason is None,
        "completion_reason": completion_reason,
        "deepest_floor": int(node.snapshot.deepest_floor),
        "floor_progress": int(floor_progress),
        "headroom": _headroom(simulator, node.snapshot),
        "minimum_headroom": float(node.minimum_headroom),
        "supported_floor": node.snapshot.supported_floor,
        "last_landed_floor": node.snapshot.last_landed_floor,
        "landing_count": int(events.get("landed", 0)),
        "support_departure_count": int(
            events.get("support_departed", 0)
        ),
        "floor_descended_count": int(events.get("floor_descended", 0)),
        "event_counts": dict(events),
        "reversals": int(node.reversals),
    }


def diagnose_search(
    simulator: ShaftSimulator,
    *,
    horizon: int,
    beam_width: int,
    forced_first_action: Action | None = None,
) -> dict[str, object]:
    """Replicate production search while exposing branch evidence.

    When ``forced_first_action`` is set, the first branch is preserved and the
    same beam width is applied to the remaining search.  Live simulator state,
    RNG state, and platform identity are restored before returning.
    """

    planner = BoundedRoutePlanner(
        horizon=int(horizon),
        beam_width=int(beam_width),
    )
    root = simulator.capture_snapshot()
    platform_ids = tuple(id(item) for item in simulator.platforms)
    root_floor = simulator.deepest_floor
    root_headroom = _headroom(simulator, root)
    root_node = _DiagnosticNode(
        snapshot=root,
        actions=(),
        score=planner._score(
            simulator,
            root_floor=root_floor,
            terminal_reason=None,
            reversals=0,
            depth=0,
        ),
        terminal_reason=None,
        reversals=0,
        events=(),
        minimum_headroom=root_headroom,
    )
    beam = [root_node]
    completed: list[_DiagnosticNode] = []
    expanded_nodes = 0
    started = perf_counter()
    try:
        for depth in range(1, planner.horizon + 1):
            candidates: list[_DiagnosticNode] = []
            for node in beam:
                if node.terminal_reason is not None:
                    completed.append(node)
                    continue
                if node.snapshot.deepest_floor > root_floor:
                    completed.append(node)
                    continue
                actions: Iterable[Action] = (
                    (forced_first_action,)
                    if depth == 1 and forced_first_action is not None
                    else tuple(Action)
                )
                for action in actions:
                    simulator.restore_snapshot(node.snapshot)
                    step_result = simulator.step(action)
                    expanded_nodes += 1
                    reversals = node.reversals + planner._reversal_count(
                        node.actions,
                        action,
                    )
                    action_sequence = node.actions + (action,)
                    child_snapshot = simulator.capture_snapshot()
                    child = _DiagnosticNode(
                        snapshot=child_snapshot,
                        actions=action_sequence,
                        score=planner._score(
                            simulator,
                            root_floor=root_floor,
                            terminal_reason=step_result.terminal_reason,
                            reversals=reversals,
                            depth=depth,
                        ),
                        terminal_reason=step_result.terminal_reason,
                        reversals=reversals,
                        events=node.events + tuple(step_result.events),
                        minimum_headroom=min(
                            node.minimum_headroom,
                            _headroom(simulator, child_snapshot),
                        ),
                    )
                    candidates.append(child)
            if not candidates:
                break
            unique: dict[tuple[object, ...], _DiagnosticNode] = {}
            for node in sorted(
                candidates,
                key=lambda item: item.score,
                reverse=True,
            ):
                unique.setdefault(planner._signature(node), node)
            beam = list(unique.values())[: planner.beam_width]
        completed.extend(beam)
        selected = max(completed, key=lambda item: item.score)
        best_by_first_action: dict[str, dict[str, object] | None] = {
            action.name: None for action in Action
        }
        for action in Action:
            branch = [
                node
                for node in completed
                if node.actions and node.actions[0] is action
            ]
            if branch:
                best_by_first_action[action.name] = _node_summary(
                    simulator,
                    max(branch, key=lambda item: item.score),
                    root_floor=root_floor,
                    horizon=planner.horizon,
                )
        payload = {
            "horizon": planner.horizon,
            "beam_width": planner.beam_width,
            "forced_first_action": (
                None
                if forced_first_action is None
                else forced_first_action.name
            ),
            "root_floor": int(root_floor),
            "root_headroom": root_headroom,
            "selected": _node_summary(
                simulator,
                selected,
                root_floor=root_floor,
                horizon=planner.horizon,
            ),
            "best_completed_by_first_action": best_by_first_action,
            "completed_nodes": len(completed),
            "expanded_nodes": expanded_nodes,
            "runtime_seconds": perf_counter() - started,
        }
    finally:
        simulator.restore_snapshot(root)
    payload["snapshot_restored"] = simulator.capture_snapshot() == root
    payload["platform_identity_restored"] = (
        tuple(id(item) for item in simulator.platforms) == platform_ids
    )
    return payload


def evaluate_action_sequence(
    simulator: ShaftSimulator,
    actions: Iterable[Action],
) -> dict[str, object]:
    root = simulator.capture_snapshot()
    platform_ids = tuple(id(item) for item in simulator.platforms)
    root_floor = simulator.deepest_floor
    sequence = tuple(actions)
    minimum_headroom = _headroom(simulator, root)
    terminal_reason = None
    events: list[str] = []
    executed: list[Action] = []
    reversals = 0
    planner = BoundedRoutePlanner()
    try:
        for action in sequence:
            reversals += planner._reversal_count(tuple(executed), action)
            result = simulator.step(action)
            executed.append(action)
            events.extend(str(event) for event in result.events)
            minimum_headroom = min(
                minimum_headroom,
                _headroom(simulator),
            )
            if result.terminal_reason is not None:
                terminal_reason = result.terminal_reason
                break
        snapshot = simulator.capture_snapshot()
        score = planner._score(
            simulator,
            root_floor=root_floor,
            terminal_reason=terminal_reason,
            reversals=reversals,
            depth=len(executed),
        )
        node = _DiagnosticNode(
            snapshot=snapshot,
            actions=tuple(executed),
            score=score,
            terminal_reason=terminal_reason,
            reversals=reversals,
            events=tuple(events),
            minimum_headroom=minimum_headroom,
        )
        payload = _node_summary(
            simulator,
            node,
            root_floor=root_floor,
            horizon=len(sequence),
        )
    finally:
        simulator.restore_snapshot(root)
    payload["snapshot_restored"] = simulator.capture_snapshot() == root
    payload["platform_identity_restored"] = (
        tuple(id(item) for item in simulator.platforms) == platform_ids
    )
    return payload


def trace_forced_path_pruning(
    simulator: ShaftSimulator,
    forced_actions: tuple[Action, ...],
    *,
    horizon: int,
    beam_width: int,
) -> dict[str, object]:
    """Locate where a known forced-branch path leaves the shared global beam."""

    if not forced_actions or len(forced_actions) > horizon:
        raise ValueError("forced_actions必須在diagnostic horizon內。")
    planner = BoundedRoutePlanner(horizon=horizon, beam_width=beam_width)
    root = simulator.capture_snapshot()
    platform_ids = tuple(id(item) for item in simulator.platforms)
    root_floor = simulator.deepest_floor
    root_headroom = _headroom(simulator, root)
    root_node = _DiagnosticNode(
        snapshot=root,
        actions=(),
        score=planner._score(
            simulator,
            root_floor=root_floor,
            terminal_reason=None,
            reversals=0,
            depth=0,
        ),
        terminal_reason=None,
        reversals=0,
        events=(),
        minimum_headroom=root_headroom,
    )

    def child(node: _DiagnosticNode, action: Action, depth: int) -> _DiagnosticNode:
        simulator.restore_snapshot(node.snapshot)
        result = simulator.step(action)
        reversals = node.reversals + planner._reversal_count(
            node.actions,
            action,
        )
        snapshot = simulator.capture_snapshot()
        return _DiagnosticNode(
            snapshot=snapshot,
            actions=node.actions + (action,),
            score=planner._score(
                simulator,
                root_floor=root_floor,
                terminal_reason=result.terminal_reason,
                reversals=reversals,
                depth=depth,
            ),
            terminal_reason=result.terminal_reason,
            reversals=reversals,
            events=node.events + tuple(result.events),
            minimum_headroom=min(
                node.minimum_headroom,
                _headroom(simulator, snapshot),
            ),
        )

    beam = [root_node]
    forced_node = root_node
    depths: list[dict[str, object]] = []
    first_pruned_depth = None
    try:
        for depth in range(1, min(horizon, len(forced_actions)) + 1):
            candidates: list[_DiagnosticNode] = []
            for node in beam:
                if (
                    node.terminal_reason is not None
                    or node.snapshot.deepest_floor > root_floor
                ):
                    continue
                for action in Action:
                    candidates.append(child(node, action, depth))
            forced_node = child(
                forced_node,
                forced_actions[depth - 1],
                depth,
            )
            unique: dict[tuple[object, ...], _DiagnosticNode] = {}
            for node in sorted(
                candidates,
                key=lambda item: item.score,
                reverse=True,
            ):
                unique.setdefault(planner._signature(node), node)
            ranked = list(unique.values())
            forced_signature = planner._signature(forced_node)
            equivalent_rank = next(
                (
                    index + 1
                    for index, node in enumerate(ranked)
                    if planner._signature(node) == forced_signature
                ),
                None,
            )
            equivalent = (
                None
                if equivalent_rank is None
                else ranked[equivalent_rank - 1]
            )
            beam = ranked[: planner.beam_width]
            in_beam = any(
                planner._signature(node) == forced_signature for node in beam
            )
            if not in_beam and first_pruned_depth is None:
                first_pruned_depth = depth
            branch_counts = Counter(
                node.actions[0].name
                for node in beam
                if node.actions
            )
            depths.append({
                "depth": depth,
                "forced_action": forced_actions[depth - 1].name,
                "forced_prefix": [
                    action.name for action in forced_node.actions
                ],
                "forced_score": float(forced_node.score),
                "forced_terminal_reason": forced_node.terminal_reason,
                "forced_deepest_floor": int(
                    forced_node.snapshot.deepest_floor
                ),
                "forced_signature_in_unique_candidates": (
                    equivalent_rank is not None
                ),
                "forced_signature_unique_rank": equivalent_rank,
                "equivalent_unique_score": (
                    None if equivalent is None else float(equivalent.score)
                ),
                "beam_cutoff_score": (
                    None if not beam else float(beam[-1].score)
                ),
                "forced_signature_in_global_beam": in_beam,
                "global_unique_candidate_count": len(ranked),
                "global_beam_size": len(beam),
                "global_beam_first_action_counts": {
                    action.name: int(branch_counts.get(action.name, 0))
                    for action in Action
                },
            })
            if not beam:
                break
        payload = {
            "horizon": horizon,
            "beam_width": beam_width,
            "forced_actions": [action.name for action in forced_actions],
            "first_pruned_depth": first_pruned_depth,
            "depths": depths,
        }
    finally:
        simulator.restore_snapshot(root)
    payload["snapshot_restored"] = simulator.capture_snapshot() == root
    payload["platform_identity_restored"] = (
        tuple(id(item) for item in simulator.platforms) == platform_ids
    )
    return payload


def _scan_terminal_risk(seed: int) -> dict[str, object]:
    if seed not in TOP_FAILURE_SEEDS:
        raise ValueError("Phase 2F只允許formal top failure seeds。")
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    env.reset(seed=seed)
    terminal_plan_steps: list[int] = []
    terminal_risk_replan_steps: list[int] = []
    terminal_reason = None
    try:
        for step in range(1, MAX_EPISODE_STEPS + 1):
            risk_before = bool(oracle._route_terminal_risk)
            planning_before = oracle.route_planning_count
            decision = oracle.choose(env.simulator)
            planned_now = oracle.route_planning_count > planning_before
            plan = oracle.last_route_plan if planned_now else None
            if plan is not None and plan.predicted_terminal is not None:
                terminal_plan_steps.append(step)
                if risk_before:
                    terminal_risk_replan_steps.append(step)
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            if terminated or truncated:
                terminal_reason = str(info["terminal_reason"])
                break
        return {
            "seed": seed,
            "terminal_plan_steps": terminal_plan_steps,
            "terminal_risk_replan_steps": terminal_risk_replan_steps,
            "terminal_step": step,
            "terminal_reason": terminal_reason,
            "deepest_floor": int(env.simulator.deepest_floor),
        }
    finally:
        env.close()


def _compact_search(search: dict[str, object]) -> dict[str, object]:
    selected = search["selected"]
    return {
        "horizon": search["horizon"],
        "beam_width": search["beam_width"],
        "forced_first_action": search["forced_first_action"],
        "selected": selected,
        "expanded_nodes": search["expanded_nodes"],
        "runtime_seconds": search["runtime_seconds"],
        "snapshot_restored": search["snapshot_restored"],
        "platform_identity_restored": search[
            "platform_identity_restored"
        ],
    }


def _forced_searches(
    simulator: ShaftSimulator,
    *,
    horizon: int,
    beam_width: int,
) -> dict[str, dict[str, object]]:
    return {
        action.name: _compact_search(diagnose_search(
            simulator,
            horizon=horizon,
            beam_width=beam_width,
            forced_first_action=action,
        ))
        for action in Action
    }


def _any_nonterminal(
    forced: dict[str, dict[str, object]],
) -> bool:
    return any(
        item["selected"]["predicted_terminal_reason"] is None
        for item in forced.values()
    )


def _state_payload(simulator: ShaftSimulator) -> dict[str, object]:
    snapshot = simulator.capture_snapshot()
    body = simulator.player.body
    return {
        "player_x": float(body.position.x),
        "player_y": float(body.position.y),
        "velocity_x": float(body.velocity.x),
        "velocity_y": float(body.velocity.y),
        "screen_top": float(
            simulator.config.height
            - (float(body.position.y) + simulator.player.height / 2)
        ),
        "headroom": _headroom(simulator, snapshot),
        "planning_scroll": float(
            simulator.config.scroll_speed
            * FORMAL_HORIZON
            * simulator.config.dt
        ),
        "deepest_floor": int(simulator.deepest_floor),
        "supported_floor": simulator.supported_floor,
        "last_landed_floor": simulator.last_landed_floor,
        "airborne": simulator.supported_floor is None,
        "health_segments": int(simulator.health_segments),
    }


def review_top_failure(
    seed: int,
    *,
    include_extended: bool = True,
) -> dict[str, object]:
    scan = _scan_terminal_risk(seed)
    terminal_plan_steps = tuple(int(value) for value in scan[
        "terminal_plan_steps"
    ])
    if not terminal_plan_steps:
        raise RuntimeError(f"seed {seed}沒有terminal-plan exposure。")
    entry_step = terminal_plan_steps[0]
    last_trigger_step = terminal_plan_steps[-1]
    timeline_start = max(1, entry_step - TIMELINE_LOOKBACK_STEPS)
    representative_extended_steps = {entry_step, last_trigger_step}

    v6_env = ShaftEnv(config=edge_fidelity_config())
    v8_env = ShaftEnv(config=edge_fidelity_config())
    v6 = OracleFull(enable_route_planner=True, route_plan_execution="cached")
    v8 = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    v6_env.reset(seed=seed)
    v8_env.reset(seed=seed)
    timeline: list[dict[str, object]] = []
    triggers: list[dict[str, object]] = []
    live_state_equal_before_all = True
    live_state_equal_after_all = True
    try:
        for step in range(1, MAX_EPISODE_STEPS + 1):
            live_state_equal_before_all &= (
                v6_env.simulator.capture_snapshot()
                == v8_env.simulator.capture_snapshot()
            )
            state = _state_payload(v8_env.simulator)
            global_search = None
            forced_base = None
            if step >= timeline_start:
                global_search = diagnose_search(
                    v8_env.simulator,
                    horizon=FORMAL_HORIZON,
                    beam_width=FORMAL_BEAM_WIDTH,
                )
                forced_base = _forced_searches(
                    v8_env.simulator,
                    horizon=FORMAL_HORIZON,
                    beam_width=FORMAL_BEAM_WIDTH,
                )

            v6_cached_before = tuple(v6._route_actions)
            v6_planning_before = v6.route_planning_count
            v8_planning_before = v8.route_planning_count
            v8_risk_before = bool(v8._route_terminal_risk)
            v6_decision = v6.choose(v6_env.simulator)
            v8_decision = v8.choose(v8_env.simulator)
            v6_planned_now = v6.route_planning_count > v6_planning_before
            v8_planned_now = v8.route_planning_count > v8_planning_before
            v6_plan = v6.last_route_plan if v6_planned_now else None
            v8_plan = v8.last_route_plan if v8_planned_now else None
            if v6_planned_now and v6_plan is not None:
                cached_suffix = tuple(v6_plan.actions)
                cached_source = "new_v6_plan"
            else:
                cached_suffix = v6_cached_before
                cached_source = "existing_v6_cached_suffix"
            cached_evaluation = evaluate_action_sequence(
                v6_env.simulator,
                cached_suffix,
            )

            is_terminal_plan = (
                v8_plan is not None
                and v8_planned_now
                and v8_plan.predicted_terminal is not None
            )
            trigger: dict[str, object] | None = None
            if is_terminal_plan:
                if global_search is None or forced_base is None:
                    raise RuntimeError("terminal trigger缺少offline search。")
                selected = global_search["selected"]
                production_actions = tuple(v8_plan.actions)
                production_matches_diagnostic = (
                    selected["actions"]
                    == [action.name for action in production_actions]
                    and selected["score"] == v8_plan.score
                    and selected["predicted_terminal_reason"]
                    == v8_plan.predicted_terminal
                )
                selected_first = production_actions[0]
                different_first_later_terminal = []
                selected_terminal_step = selected["terminal_step"]
                for action_name, item in forced_base.items():
                    candidate = item["selected"]
                    if (
                        action_name != selected_first.name
                        and candidate["terminal_step"] is not None
                        and selected_terminal_step is not None
                        and candidate["terminal_step"]
                        > selected_terminal_step
                    ):
                        different_first_later_terminal.append(action_name)
                extended: dict[str, object] = {}
                if include_extended and not _any_nonterminal(forced_base):
                    for horizon, beam_width in ((24, 24), (12, 96)):
                        key = f"h{horizon}_b{beam_width}"
                        extended[key] = _forced_searches(
                            v8_env.simulator,
                            horizon=horizon,
                            beam_width=beam_width,
                        )
                    if (
                        step in representative_extended_steps
                        and not any(
                            _any_nonterminal(value)
                            for value in extended.values()
                        )
                    ):
                        extended["h24_b96"] = _forced_searches(
                            v8_env.simulator,
                            horizon=24,
                            beam_width=96,
                        )
                trigger = {
                    "seed": seed,
                    "episode_step": step,
                    "trigger_kind": (
                        "terminal_risk_replan"
                        if v8_risk_before
                        else "terminal_risk_entry"
                    ),
                    "player_state": state,
                    "support_state": {
                        "supported_floor": state["supported_floor"],
                        "last_landed_floor": state["last_landed_floor"],
                        "airborne": state["airborne"],
                    },
                    "cached_plan_source": cached_source,
                    "cached_plan_suffix": [
                        action.name for action in cached_suffix
                    ],
                    "cached_first_action": v6_decision.action.name,
                    "cached_suffix_evaluation": cached_evaluation,
                    "terminal_prediction_reason": (
                        v8_plan.predicted_terminal
                    ),
                    "formal_global_search": global_search,
                    "forced_first_actions": forced_base,
                    "selected_candidate": selected,
                    "selected_first_action": selected_first.name,
                    "same_as_v6_cached_action": (
                        selected_first is v6_decision.action
                    ),
                    "different_suffix_same_first_action": (
                        bool(cached_suffix)
                        and selected_first is cached_suffix[0]
                        and production_actions != cached_suffix
                    ),
                    "nonterminal_candidate_exists_h12_b24": (
                        _any_nonterminal(forced_base)
                    ),
                    "different_first_action_dies_later": (
                        different_first_later_terminal
                    ),
                    "production_plan_matches_diagnostic": (
                        production_matches_diagnostic
                    ),
                    "terminal_suffix_not_cached_by_design": (
                        tuple(v8._route_actions) == ()
                    ),
                    "extended_diagnostics": extended,
                }

            old_step = v6_env.step(int(v6_decision.action))
            new_step = v8_env.step(int(v8_decision.action))
            state_equal_after = (
                v6_env.simulator.capture_snapshot()
                == v8_env.simulator.capture_snapshot()
            )
            live_state_equal_after_all &= state_equal_after
            if trigger is not None:
                trigger["executed_action"] = v8_decision.action.name
                trigger["selected_first_action_executed"] = (
                    v8_decision.action.name
                    == trigger["selected_first_action"]
                )
                trigger["paired_state_equal_after_execution"] = (
                    state_equal_after
                )
                triggers.append(trigger)

            if step >= timeline_start:
                if global_search is None or forced_base is None:
                    raise RuntimeError("timeline search缺失。")
                timeline.append({
                    "step": step,
                    "headroom": state["headroom"],
                    "supported_floor": state["supported_floor"],
                    "airborne": state["airborne"],
                    "v6_cached_actions_before": len(v6_cached_before),
                    "v6_action": v6_decision.action.name,
                    "v8_action": v8_decision.action.name,
                    "v8_planned_now": v8_planned_now,
                    "v8_terminal_risk_before": v8_risk_before,
                    "v8_terminal_plan_now": is_terminal_plan,
                    "offline_global_terminal": (
                        global_search["selected"][
                            "predicted_terminal_reason"
                        ]
                    ),
                    "offline_global_first_action": (
                        global_search["selected"]["first_action"]
                    ),
                    "forced_first_any_nonterminal": _any_nonterminal(
                        forced_base
                    ),
                    "forced_first_max_survival_steps": max(
                        int(item["selected"][
                            "survival_steps_before_terminal"
                        ])
                        for item in forced_base.values()
                    ),
                    "forced_first_terminal_steps": {
                        action: item["selected"]["terminal_step"]
                        for action, item in forced_base.items()
                    },
                    "cached_suffix_length": len(cached_suffix),
                    "cached_suffix_terminal": cached_evaluation[
                        "predicted_terminal_reason"
                    ],
                    "cached_suffix_minimum_headroom": cached_evaluation[
                        "minimum_headroom"
                    ],
                })
            terminated = bool(old_step[2] or old_step[3])
            if terminated:
                break

        persistent_unavoidable_step = None
        for index, row in enumerate(timeline):
            if all(
                not later["forced_first_any_nonterminal"]
                for later in timeline[index:]
            ):
                persistent_unavoidable_step = int(row["step"])
                break
        last_rescuable_step = max(
            (
                int(row["step"])
                for row in timeline
                if row["forced_first_any_nonterminal"]
                and (
                    persistent_unavoidable_step is None
                    or int(row["step"]) < persistent_unavoidable_step
                )
            ),
            default=None,
        )
        first_offline_terminal_step = next(
            (
                int(row["step"])
                for row in timeline
                if row["offline_global_terminal"] is not None
            ),
            None,
        )
        timing = {
            "reviewed_step_start": timeline_start,
            "last_rescuable_step_within_forced_h12_b24": (
                last_rescuable_step
            ),
            "first_persistently_unavoidable_step_h12_b24": (
                persistent_unavoidable_step
            ),
            "first_offline_binary_terminal_prediction_step": (
                first_offline_terminal_step
            ),
            "v8_terminal_risk_entry_step": entry_step,
            "decisions_from_last_rescuable_to_v8_entry": (
                None
                if last_rescuable_step is None
                else entry_step - last_rescuable_step
            ),
            "binary_terminal_lag_after_unavoidable": (
                None
                if persistent_unavoidable_step is None
                or first_offline_terminal_step is None
                else first_offline_terminal_step
                - persistent_unavoidable_step
            ),
            "trigger_has_surviving_candidate_h12_b24": next(
                bool(row["forced_first_any_nonterminal"])
                for row in timeline
                if int(row["step"]) == entry_step
            ),
            "trigger_too_late_under_bounded_survival_definition": (
                not next(
                    bool(row["forced_first_any_nonterminal"])
                    for row in timeline
                    if int(row["step"]) == entry_step
                )
            ),
            "survival_margin_definition": (
                "at least one forced-first branch remains nonterminal or "
                "reaches a deeper floor within isolated 12-step/24-beam "
                "search"
            ),
        }
        return {
            "seed": seed,
            "formal_scan": scan,
            "timeline": timeline,
            "trigger_timing": timing,
            "terminal_triggers": triggers,
            "integrity": {
                "v6_v8_state_equal_before_every_decision": (
                    live_state_equal_before_all
                ),
                "v6_v8_state_equal_after_every_decision": (
                    live_state_equal_after_all
                ),
                "all_search_snapshots_restored": all(
                    trigger["formal_global_search"]["snapshot_restored"]
                    and trigger["formal_global_search"][
                        "platform_identity_restored"
                    ]
                    and all(
                        item["snapshot_restored"]
                        and item["platform_identity_restored"]
                        for item in trigger["forced_first_actions"].values()
                    )
                    for trigger in triggers
                ),
                "all_production_plans_match_diagnostic": all(
                    trigger["production_plan_matches_diagnostic"]
                    for trigger in triggers
                ),
                "all_selected_first_actions_executed": all(
                    trigger["selected_first_action_executed"]
                    for trigger in triggers
                ),
            },
        }
    finally:
        v6_env.close()
        v8_env.close()


def run_committed_branch_counterfactual(
    *,
    seed: int,
    trigger_step: int,
    forced_first_action: Action,
) -> dict[str, object]:
    """Commit one isolated forced-first plan, then resume a fresh v8 oracle.

    This is diagnostic-only.  It does not alter or instantiate a new
    production policy version and it accepts only the two exposed top-failure
    development seeds.
    """

    if seed not in TOP_FAILURE_SEEDS:
        raise ValueError("Phase 2F counterfactual只允許top failure seeds。")
    if trigger_step < 1 or trigger_step > MAX_EPISODE_STEPS:
        raise ValueError("trigger_step超出bounded episode。")
    env = ShaftEnv(config=edge_fidelity_config())
    replay_oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    env.reset(seed=seed)
    total_steps = 0
    terminal_reason: str | None = None
    try:
        for step in range(1, trigger_step):
            decision = replay_oracle.choose(env.simulator)
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            total_steps = step
            if terminated or truncated:
                raise RuntimeError(
                    f"seed {seed}在counterfactual trigger前已終局。"
                )
        root_floor = int(env.simulator.deepest_floor)
        root_state = _state_payload(env.simulator)
        branch = diagnose_search(
            env.simulator,
            horizon=FORMAL_HORIZON,
            beam_width=FORMAL_BEAM_WIDTH,
            forced_first_action=forced_first_action,
        )
        planned_actions = tuple(
            Action[name] for name in branch["selected"]["actions"]
        )
        executed_actions: list[str] = []
        branch_terminal_reason = None
        branch_floor = root_floor
        for action in planned_actions:
            _, _, terminated, truncated, info = env.step(int(action))
            total_steps += 1
            executed_actions.append(action.name)
            branch_floor = int(env.simulator.deepest_floor)
            if env.simulator.deepest_floor >= 10:
                terminal_reason = "target_reached"
                break
            if terminated or truncated:
                branch_terminal_reason = str(info["terminal_reason"])
                terminal_reason = branch_terminal_reason
                break

        continuation_planning_count = 0
        if terminal_reason is None:
            continuation = OracleFull(
                enable_route_planner=True,
                route_plan_execution="terminal_guarded",
            )
            while total_steps < MAX_EPISODE_STEPS:
                decision = continuation.choose(env.simulator)
                _, _, terminated, truncated, info = env.step(
                    int(decision.action)
                )
                total_steps += 1
                if env.simulator.deepest_floor >= 10:
                    terminal_reason = "target_reached"
                    break
                if terminated or truncated:
                    terminal_reason = str(info["terminal_reason"])
                    break
            continuation_planning_count = continuation.route_planning_count
        return {
            "seed": seed,
            "trigger_step": trigger_step,
            "forced_first_action": forced_first_action.name,
            "root_floor": root_floor,
            "root_state": root_state,
            "branch_search": branch,
            "branch_actions_executed": executed_actions,
            "branch_predicted_terminal": branch["selected"][
                "predicted_terminal_reason"
            ],
            "branch_terminal_reason": branch_terminal_reason,
            "branch_floor_after_execution": branch_floor,
            "branch_advanced_floor": branch_floor > root_floor,
            "continuation_policy": (
                "fresh oracle-full-v8-terminal-risk-guard"
            ),
            "continuation_planning_count": continuation_planning_count,
            "final_deepest_floor": int(env.simulator.deepest_floor),
            "final_terminal_reason": terminal_reason,
            "reached_floor_10": env.simulator.deepest_floor >= 10,
            "total_episode_steps": total_steps,
            "formal_gate": False,
            "diagnostic_only": True,
        }
    finally:
        env.close()


__all__ = [
    "FORMAL_BEAM_WIDTH",
    "FORMAL_HORIZON",
    "TIMELINE_LOOKBACK_STEPS",
    "TOP_FAILURE_SEEDS",
    "diagnose_search",
    "evaluate_action_sequence",
    "review_top_failure",
    "run_committed_branch_counterfactual",
    "trace_forced_path_pruning",
]
