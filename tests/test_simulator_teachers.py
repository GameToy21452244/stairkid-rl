from __future__ import annotations

from inspect import signature

import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.observation import GameObservation
from stair_agent.policies.simulator_teachers import (
    SIMULATOR_TEACHER_PROFILES,
    TEACHER_POLICY_VERSION,
    OracleFull,
    TeacherObservable,
)


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
        assert decision.policy_version == TEACHER_POLICY_VERSION
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
    assert decision.target_signed_offset is not None
    assert decision.target_signed_offset > 0.0


def test_simulator_teacher_profiles_are_explicit_and_versioned() -> None:
    assert set(SIMULATOR_TEACHER_PROFILES) == {
        "current",
        "departure_delayed",
        "departure_disabled",
        "departure_delayed_launch_handoff",
    }
    versions = {
        profile.policy_version
        for profile in SIMULATOR_TEACHER_PROFILES.values()
    }

    assert len(versions) == 4
    assert all("simulator" in version for version in versions)
    assert SIMULATOR_TEACHER_PROFILES["current"].departure_delay_steps == 0
    assert SIMULATOR_TEACHER_PROFILES["departure_delayed"].departure_delay_steps == 2
    assert not SIMULATOR_TEACHER_PROFILES["departure_disabled"].departure_enabled
    assert SIMULATOR_TEACHER_PROFILES[
        "departure_delayed_launch_handoff"
    ].support_aware_launch_handoff_enabled


def test_teacher_decision_carries_selected_simulator_profile_version() -> None:
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
        health={"segments": 12, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=[],
    )
    profile = SIMULATOR_TEACHER_PROFILES["departure_delayed"]
    decision = TeacherObservable(profile=profile).choose(observation)

    assert decision.policy_version == profile.policy_version
