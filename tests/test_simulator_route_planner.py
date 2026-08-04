from __future__ import annotations

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.policies.simulator_route_planner import BoundedRoutePlanner
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


def _move_player_into_route_trigger(env: ShaftEnv) -> None:
    simulator = env.simulator
    source = simulator.supported_platform
    assert source is not None
    desired_screen_center_y = 180.0
    desired_world_center_y = env.config.height - desired_screen_center_y
    source.body.position = (
        source.body.position.x,
        desired_world_center_y
        - simulator.player.height / 2
        - source.height / 2,
    )
    simulator.player.body.position = (
        simulator.player.body.position.x,
        desired_world_center_y,
    )


def test_snapshot_restore_replays_identical_step() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    try:
        env.reset(seed=15000)
        simulator = env.simulator
        before = simulator.capture_snapshot()
        first = simulator.step(Action.RIGHT)
        first_after = simulator.capture_snapshot()

        simulator.restore_snapshot(before)
        assert simulator.capture_snapshot() == before
        second = simulator.step(Action.RIGHT)
        second_after = simulator.capture_snapshot()

        assert second == first
        assert second_after == first_after
    finally:
        env.close()


def test_route_planner_choose_restores_live_simulator_state() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    oracle = OracleFull(enable_route_planner=True)
    try:
        env.reset(seed=15001)
        simulator = env.simulator
        source = simulator.supported_platform
        assert source is not None
        desired_screen_center_y = 180.0
        desired_world_center_y = env.config.height - desired_screen_center_y
        source.body.position = (
            source.body.position.x,
            desired_world_center_y
            - simulator.player.height / 2
            - source.height / 2,
        )
        simulator.player.body.position = (
            simulator.player.body.position.x,
            desired_world_center_y,
        )
        recycle_probe = simulator.platforms[-1]
        recycle_probe.body.position = (
            recycle_probe.body.position.x,
            env.config.height + env.config.recycle_margin,
        )
        platform_ids = tuple(id(platform) for platform in simulator.platforms)
        before = simulator.capture_snapshot()

        oracle.choose(simulator)

        assert simulator.capture_snapshot() == before
        assert tuple(id(platform) for platform in simulator.platforms) == platform_ids
        assert oracle.route_planning_count == 1
        assert oracle.last_route_plan is not None
        assert oracle.last_route_plan.expanded_nodes <= 3 * 12 * 24
        assert oracle.last_route_plan.horizon == 12
        assert oracle.last_route_plan.beam_width == 24
    finally:
        env.close()


def test_route_rollout_records_every_departure_at_event_time() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    oracle = OracleFull(enable_route_planner=True)
    departures = 0
    try:
        env.reset(seed=13003)
        for _ in range(100):
            decision = oracle.choose(env.simulator)
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            event_count = info["events"].count("support_departed")
            records = info["support_departures"]
            assert len(records) == event_count
            assert all(record["clearance"] >= 0.0 for record in records)
            departures += event_count
            if env.simulator.deepest_floor >= 10 or terminated or truncated:
                break

        assert departures > 0
    finally:
        env.close()


def test_route_planner_repairs_fixed_v5_top_failure() -> None:
    def rollout(enabled: bool) -> tuple[int, str | None]:
        env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
        oracle = OracleFull(enable_route_planner=enabled)
        terminal = None
        try:
            env.reset(seed=13009)
            for _ in range(100):
                decision = oracle.choose(env.simulator)
                _, _, terminated, truncated, info = env.step(
                    int(decision.action)
                )
                if env.simulator.deepest_floor >= 10:
                    terminal = "target_reached"
                    break
                if terminated or truncated:
                    terminal = info["terminal_reason"]
                    break
            return env.simulator.deepest_floor, terminal
        finally:
            env.close()

    assert rollout(False) == (6, "top")
    planned_floor, planned_terminal = rollout(True)
    assert planned_floor >= 10
    assert planned_terminal == "target_reached"


def test_v7_receding_mode_matches_v5_before_trigger() -> None:
    config = edge_fidelity_config()
    v5_env = ShaftEnv(config=config)
    v7_env = ShaftEnv(config=config)
    v5 = OracleFull(enable_route_planner=False)
    v7 = OracleFull(
        enable_route_planner=True,
        route_plan_execution="receding",
    )
    try:
        v5_env.reset(seed=16000)
        v7_env.reset(seed=16000)
        assert not BoundedRoutePlanner().should_plan(v7_env.simulator)

        expected = v5.choose(v5_env.simulator)
        actual = v7.choose(v7_env.simulator)

        assert actual.action is expected.action
        assert actual.target_platform_id == expected.target_platform_id
        assert v7.route_planning_count == 0
        assert v7.last_route_plan is None
    finally:
        v5_env.close()
        v7_env.close()


def test_v7_receding_mode_executes_only_current_plan_first_action() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="receding",
    )
    try:
        env.reset(seed=16001)
        _move_player_into_route_trigger(env)
        simulator = env.simulator
        before = simulator.capture_snapshot()
        expected_plan = BoundedRoutePlanner().plan(simulator)
        platform_ids = tuple(id(item) for item in simulator.platforms)

        decision = oracle.choose(simulator)

        assert expected_plan.actions
        assert decision.action is expected_plan.actions[0]
        assert oracle.policy_version == (
            "oracle-full-v7-receding-route-planner"
        )
        assert oracle.route_planning_count == 1
        assert oracle.last_route_plan == expected_plan
        assert oracle._route_actions == ()
        assert simulator.capture_snapshot() == before
        assert tuple(id(item) for item in simulator.platforms) == platform_ids
        assert oracle.last_route_plan.horizon == 12
        assert oracle.last_route_plan.beam_width == 24
        assert oracle.last_route_plan.expanded_nodes <= 3 * 12 * 24
    finally:
        env.close()


def test_v7_receding_mode_replans_on_next_decision() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="receding",
    )
    try:
        env.reset(seed=16002)
        _move_player_into_route_trigger(env)

        first = oracle.choose(env.simulator)
        assert oracle.route_planning_count == 1
        assert oracle._route_actions == ()
        env.step(int(first.action))
        assert BoundedRoutePlanner().should_plan(env.simulator)

        oracle.choose(env.simulator)
        assert oracle.route_planning_count == 2
        assert oracle._route_actions == ()
    finally:
        env.close()


def test_route_plan_execution_rejects_unknown_mode() -> None:
    try:
        OracleFull(
            enable_route_planner=True,
            route_plan_execution="unknown",
        )
    except ValueError as exc:
        assert "route_plan_execution" in str(exc)
    else:
        raise AssertionError("未知 route execution mode 應被拒絕。")


def test_v8_non_terminal_route_matches_v6_cached_trajectory() -> None:
    v6_env = ShaftEnv(config=edge_fidelity_config())
    v8_env = ShaftEnv(config=edge_fidelity_config())
    v6 = OracleFull(enable_route_planner=True)
    v8 = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    try:
        v6_env.reset(seed=16000)
        v8_env.reset(seed=16000)
        for _ in range(100):
            old = v6.choose(v6_env.simulator)
            new = v8.choose(v8_env.simulator)
            assert new.action is old.action
            assert v8_env.simulator.capture_snapshot() == (
                v6_env.simulator.capture_snapshot()
            )
            old_step = v6_env.step(int(old.action))
            new_step = v8_env.step(int(new.action))
            assert new_step[2:] == old_step[2:]
            if v6_env.simulator.deepest_floor >= 10 or old_step[2]:
                break
        assert v8.policy_version == "oracle-full-v8-terminal-risk-guard"
        assert not v8._route_terminal_risk
    finally:
        v6_env.close()
        v8_env.close()


def test_v8_terminal_plan_enters_bounded_replanning() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    oracle = OracleFull(
        enable_route_planner=True,
        route_plan_execution="terminal_guarded",
    )
    try:
        env.reset(seed=16002)
        found = False
        for _ in range(100):
            before_count = oracle.route_planning_count
            decision = oracle.choose(env.simulator)
            plan = oracle.last_route_plan
            if (
                oracle.route_planning_count > before_count
                and plan is not None
                and plan.predicted_terminal is not None
            ):
                found = True
                assert oracle._route_terminal_risk
                assert oracle._route_actions == ()
                assert decision.action is plan.actions[0]
                assert plan.horizon == 12
                assert plan.beam_width == 24
                assert plan.expanded_nodes <= 3 * 12 * 24
                env.step(int(decision.action))
                if oracle._route_planner.should_plan(env.simulator):
                    previous = oracle.route_planning_count
                    state = env.simulator.capture_snapshot()
                    oracle.choose(env.simulator)
                    assert oracle.route_planning_count == previous + 1
                    assert env.simulator.capture_snapshot() == state
                break
            _, _, terminated, truncated, _ = env.step(int(decision.action))
            if terminated or truncated:
                break
        assert found
    finally:
        env.close()
