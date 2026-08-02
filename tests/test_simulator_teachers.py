from __future__ import annotations

from inspect import signature

import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.observation import GameObservation
from stair_agent.policies.simulator_teachers import OracleFull, TeacherObservable


def test_oracle_full_uses_privileged_simulator_and_reports_rollout_values() -> None:
    env = ShaftEnv()
    try:
        env.reset(seed=501)
        decision = OracleFull().choose(env.simulator)
        assert env.action_space.contains(int(decision.action))
        assert decision.target_platform_id == 1
        assert len(decision.candidate_action_values) == 3
    finally:
        env.close()


def test_teacher_observable_api_cannot_accept_simulator_state() -> None:
    env = ShaftEnv()
    teacher = TeacherObservable()
    try:
        env.reset(seed=502)
        parameters = list(signature(teacher.choose).parameters)
        assert parameters == ["observation"]
        decision = teacher.choose(env.last_observation)
        assert env.action_space.contains(int(decision.action))
        assert sum(decision.action_distribution) == pytest.approx(1.0)
        assert 0.0 < decision.confidence < 1.0
        assert decision.teacher_type == "teacher_observable"
        assert not decision.verified
    finally:
        env.close()


def test_teacher_observable_uses_visible_health_for_recovery_target() -> None:
    observation = GameObservation(
        timestamp=0.0,
        phase="playing",
        player={
            "center_x": 200.0,
            "center_y": 150.0,
            "velocity_x": 0.0,
            "velocity_y": 30.0,
            "motion": "falling",
            "confidence": 1.0,
        },
        health={"segments": 7, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=[
            {
                "track_id": 1,
                "kind": "normal",
                "box": {"left": 240, "top": 180, "width": 96, "height": 16},
            },
            {
                "track_id": 2,
                "kind": "normal",
                "box": {"left": 80, "top": 280, "width": 96, "height": 16},
            },
        ],
        platform_scroll_velocity_y=0.0,
        events=[],
    )

    decision = TeacherObservable(verified=True).choose(observation)

    assert decision.target_platform_id == 1
    assert int(decision.action) == 2
