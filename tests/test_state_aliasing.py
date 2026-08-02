from __future__ import annotations

import numpy as np

from stair_agent.state_aliasing import (
    ACTION_NAMES,
    AuditRow,
    align_episode_rows,
    build_memory_matrix,
    cross_episode_knn,
)


def _transition(step: int, action: int) -> dict:
    observation = [0.0] * 268
    observation[0] = 1.0
    observation[1] = float(step)
    return {
        "episode_id": "episode-test",
        "step": step,
        "observation": observation,
        "action": action,
        "target_platform_kind": "normal",
        "target_signed_offset": 12.0,
    }


def _controller(step: int, action: str, *, phase: str) -> dict:
    return {
        "step": step,
        "action": action,
        "teacher_reason": phase,
        "control_loop_hz": 8.0,
        "controller_memory": {
            "controller_phase": phase,
            "previous_action": action,
            "action_streak_steps": step + 1,
            "target_platform_id": 100 + step,
            "support_platform_id": 200 + step,
            "recovery_active": False,
        },
    }


def test_alignment_uses_previous_post_decision_memory_as_causal_input() -> None:
    transitions = [_transition(0, 2), _transition(1, 0)]
    controllers = [
        _controller(0, "RIGHT", phase="move"),
        _controller(1, "RELEASE_ALL", phase="brake"),
    ]

    rows = align_episode_rows(
        transitions,
        controllers,
        episode="episode_01",
        source="run/episode_01",
    )

    assert rows[0].causal_memory == {}
    assert rows[1].causal_memory["previous_action"] == "RIGHT"
    assert rows[1].post_memory["previous_action"] == "RELEASE_ALL"
    assert rows[1].action_name == "RELEASE_ALL"


def test_memory_encoder_excludes_unstable_track_ids() -> None:
    memories = [
        {
            "target_platform_id": 7,
            "support_platform_id": 4,
            "special_contact_episode_id": 2,
            "target_platform_kind": "spring",
            "target_lock_age_steps": 3,
        }
    ]

    matrix, columns, excluded = build_memory_matrix(memories)

    assert matrix.shape[0] == 1
    assert any(name.startswith("target_platform_kind=") for name in columns)
    assert "target_lock_age_steps" in columns
    assert "target_platform_id" in excluded
    assert "support_platform_id" in excluded
    assert "special_contact_episode_id" in excluded
    assert not any(name.endswith("_id") for name in columns)


def test_cross_episode_knn_never_uses_same_episode() -> None:
    observations = np.asarray([[0.0], [0.1], [0.2], [0.3]], dtype=np.float64)
    episodes = np.asarray(["a", "a", "b", "b"])

    result = cross_episode_knn(observations, episodes, k=1)

    assert result.indices.shape == (4, 1)
    for row_index, neighbor_index in enumerate(result.indices[:, 0]):
        assert episodes[row_index] != episodes[neighbor_index]


def test_action_mapping_is_explicit_and_stable() -> None:
    assert ACTION_NAMES == {0: "RELEASE_ALL", 1: "LEFT", 2: "RIGHT"}


def test_audit_row_records_post_and_causal_memory_separately() -> None:
    row = AuditRow(
        episode="episode_01",
        source="run/episode_01",
        step=0,
        observation=np.zeros(268),
        action=2,
        action_name="RIGHT",
        teacher_reason="move",
        controller_phase="move",
        target_kind="normal",
        special_kind=None,
        target_direction="right",
        control_loop_hz=8.0,
        post_memory={"previous_action": "RIGHT"},
        causal_memory={},
    )
    assert row.post_memory != row.causal_memory
