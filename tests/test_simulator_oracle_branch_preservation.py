from __future__ import annotations

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.policies.simulator_route_planner import BoundedRoutePlanner
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.training.simulator_v03_edge_gate import (
    MAX_EPISODE_STEPS,
    edge_fidelity_config,
)


RESCUE_TRIGGERS = (
    (16002, 39),
    (16002, 40),
    (16002, 41),
    (16002, 42),
    (16002, 43),
    (16002, 44),
    (16002, 45),
    (16002, 46),
    (16030, 51),
    (16030, 52),
    (16030, 53),
    (16030, 54),
    (16030, 55),
    (16030, 56),
)


def _replay_v8_to(seed: int, decision_step: int) -> ShaftEnv:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    env.reset(seed=seed)
    for _ in range(1, decision_step):
        decision = oracle.choose(env.simulator)
        _, _, terminated, truncated, _ = env.step(int(decision.action))
        assert not terminated and not truncated
    return env


def _run_actions(seed: int, execution: str) -> tuple[list[Action], OracleFull]:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution=execution,
    )
    env.reset(seed=seed)
    actions: list[Action] = []
    try:
        for _ in range(MAX_EPISODE_STEPS):
            decision = oracle.choose(env.simulator)
            actions.append(decision.action)
            _, _, terminated, truncated, _ = env.step(int(decision.action))
            if env.simulator.deepest_floor >= 10 or terminated or truncated:
                break
        return actions, oracle
    finally:
        env.close()


def test_first_action_lanes_are_independent_and_bounded() -> None:
    env = _replay_v8_to(16002, 39)
    try:
        planner = BoundedRoutePlanner()
        before = env.simulator.capture_snapshot()
        platform_ids = tuple(id(item) for item in env.simulator.platforms)
        result = planner.plan_first_action_lanes(env.simulator)
        assert [item.action for item in result.lanes] == list(Action)
        assert all(item.plan.actions[0] is item.action for item in result.lanes)
        assert all(item.plan.horizon == 12 for item in result.lanes)
        assert all(item.plan.beam_width == 24 for item in result.lanes)
        assert all(item.plan.expanded_nodes <= 793 for item in result.lanes)
        assert result.expanded_nodes <= 2379
        assert result.structural_peak_node_cap == 364
        assert result.runtime_seconds <= 5.0
        assert env.simulator.capture_snapshot() == before
        assert tuple(id(item) for item in env.simulator.platforms) == platform_ids
    finally:
        env.close()


def test_existing_selector_finds_all_phase2f_rescue_branches() -> None:
    for seed, step in RESCUE_TRIGGERS:
        env = _replay_v8_to(seed, step)
        try:
            result = BoundedRoutePlanner().plan_first_action_lanes(
                env.simulator
            )
            assert result.selected.actions[0] is Action.RIGHT
            assert result.selected.predicted_terminal is None
        finally:
            env.close()


def test_non_terminal_candidate_path_is_action_identical_to_v6() -> None:
    reference, _ = _run_actions(16000, "cached")
    candidate, oracle = _run_actions(16000, "branch_preserved")
    assert candidate == reference
    assert oracle.branch_preserved_search_count == 0


def test_selected_suffix_is_cached_and_executed_without_lane_switch() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="branch_preserved",
    )
    env.reset(seed=16002)
    try:
        for _ in range(1, 39):
            decision = oracle.choose(env.simulator)
            env.step(int(decision.action))
        first = oracle.choose(env.simulator).action
        assert oracle.branch_preserved_search_count == 1
        assert oracle.last_branch_search is not None
        selected = oracle.last_branch_search.selected
        assert first is selected.actions[0]
        assert oracle._route_actions == selected.actions[1:]
        env.step(int(first))
        branch_count = oracle.branch_preserved_search_count
        second = oracle.choose(env.simulator).action
        assert second is selected.actions[1]
        assert oracle.branch_preserved_search_count == branch_count
    finally:
        env.close()


def test_all_terminal_fallback_uses_existing_selector_and_full_suffix() -> None:
    env = _replay_v8_to(16002, 47)
    try:
        result = BoundedRoutePlanner().plan_first_action_lanes(env.simulator)
        assert all(
            item.plan.predicted_terminal is not None for item in result.lanes
        )
        expected = max((item.plan for item in result.lanes), key=lambda p: p.score)
        assert result.selected == expected
        assert result.selected.actions
    finally:
        env.close()


def test_branch_search_duplicate_replay_is_deterministic() -> None:
    env = _replay_v8_to(16030, 51)
    try:
        planner = BoundedRoutePlanner()
        first = planner.plan_first_action_lanes(env.simulator)
        second = planner.plan_first_action_lanes(env.simulator)
        assert first.selected == second.selected
        assert tuple(item.plan for item in first.lanes) == tuple(
            item.plan for item in second.lanes
        )
        assert first.expanded_nodes == second.expanded_nodes
    finally:
        env.close()


def test_unknown_execution_mode_still_fails_closed() -> None:
    try:
        OracleFull(
            enable_route_planner=True,
            route_plan_execution="branch_preserved_typo",
        )
    except ValueError as exc:
        assert "route_plan_execution" in str(exc)
    else:
        raise AssertionError("未知mode必須拒絕。")
