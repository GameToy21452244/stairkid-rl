from __future__ import annotations

import hashlib
import json
from pathlib import Path

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.policies.simulator_route_planner import BoundedRoutePlanner
from stair_agent.training.simulator_oracle_v8_phase2f import (
    TOP_FAILURE_SEEDS,
    diagnose_search,
    run_committed_branch_counterfactual,
    trace_forced_path_pruning,
)
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


def test_phase2f_seeds_exclude_holdout_and_bottom_failures() -> None:
    assert TOP_FAILURE_SEEDS == (16002, 16030)
    assert not set(TOP_FAILURE_SEEDS) & set(range(17000, 17100))


def test_diagnostic_search_restores_snapshot_and_matches_production() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    try:
        env.reset(seed=16002)
        simulator = env.simulator
        before = simulator.capture_snapshot()
        platform_ids = tuple(id(item) for item in simulator.platforms)
        expected = BoundedRoutePlanner().plan(simulator)
        actual = diagnose_search(simulator, horizon=12, beam_width=24)
        assert actual["selected"]["actions"] == [
            action.name for action in expected.actions
        ]
        assert actual["selected"]["predicted_terminal_reason"] == (
            expected.predicted_terminal
        )
        assert actual["selected"]["score"] == expected.score
        assert actual["snapshot_restored"]
        assert simulator.capture_snapshot() == before
        assert tuple(id(item) for item in simulator.platforms) == platform_ids
    finally:
        env.close()


def test_forced_first_diagnostic_preserves_requested_branch() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    try:
        env.reset(seed=16030)
        before = env.simulator.capture_snapshot()
        for action in Action:
            result = diagnose_search(
                env.simulator,
                horizon=12,
                beam_width=24,
                forced_first_action=action,
            )
            assert result["selected"]["first_action"] == action.name
            assert result["selected"]["actions"][0] == action.name
            assert result["snapshot_restored"]
            assert env.simulator.capture_snapshot() == before
    finally:
        env.close()


def test_committed_branch_counterfactual_is_bounded_to_top_failures() -> None:
    try:
        run_committed_branch_counterfactual(
            seed=17000,
            trigger_step=1,
            forced_first_action=Action.RIGHT,
        )
    except ValueError as exc:
        assert "top failure" in str(exc)
    else:
        raise AssertionError("holdout seed應被Phase 2F診斷拒絕。")


def test_forced_path_pruning_trace_restores_live_state() -> None:
    env = ShaftEnv(config=edge_fidelity_config())
    try:
        env.reset(seed=16002)
        before = env.simulator.capture_snapshot()
        forced = diagnose_search(
            env.simulator,
            horizon=12,
            beam_width=24,
            forced_first_action=Action.RIGHT,
        )
        trace = trace_forced_path_pruning(
            env.simulator,
            tuple(Action[name] for name in forced["selected"]["actions"]),
            horizon=12,
            beam_width=24,
        )
        assert trace["depths"]
        assert trace["depths"][0]["depth"] == 1
        assert trace["snapshot_restored"]
        assert env.simulator.capture_snapshot() == before
    finally:
        env.close()


def test_phase2f_review_artifact_preserves_frozen_evidence_and_holdout() -> None:
    artifact = json.loads(
        Path("artifacts/simulator_oracle_v8_phase2f_review_v1.json").read_text(
            encoding="utf-8"
        )
    )
    formal = Path("artifacts/simulator_oracle_v8_terminal_guard_development_v1.json")
    assert artifact["review_completed"] is True
    assert artifact["formal_v8_status_unchanged"] == "FAIL_STOP_V8_DEVELOPMENT"
    assert artifact["project_status"] == "BLOCKED_WITH_EVIDENCE"
    assert artifact["holdout"] == {
        "partition": "17000-17099",
        "used": False,
        "reachability": None,
        "oracle": None,
        "observable": None,
    }
    assert artifact["candidate_directions"][
        "D_forced_first_action_diversity_branch_preservation"
    ]["rating"] == "SUPPORTED_FOR_NEW_PROTOCOL"
    assert artifact["core_diagnosis"]["rejected_classifications"][
        "TRIGGER_TOO_LATE"
    ]
    assert hashlib.sha256(formal.read_bytes()).hexdigest() == (
        "b36273b3fb283006d0115ca025df32ed6a8ac8c3ce9d08dbe3d4b4383d7ea166"
    )
