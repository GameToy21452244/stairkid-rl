import json
from pathlib import Path

import numpy as np
import pytest

from stair_agent.data.schema import OBSERVATION_DIM, PolicySource
from stair_agent.data.writer import ActionTiming, TransitionJsonlWriter


def timing(start: float) -> ActionTiming:
    return ActionTiming(start + 0.01, start + 0.02, start + 0.10, False, 80.0)


def test_writer_creates_valid_continuous_episode(tmp_path: Path) -> None:
    path = tmp_path / "transitions.jsonl"
    first = np.zeros(OBSERVATION_DIM, dtype=np.float32)
    second = np.full(OBSERVATION_DIM, 0.1, dtype=np.float32)
    writer = TransitionJsonlWriter(
        path,
        policy_source=PolicySource.BASELINE,
        episode_id="ep-1",
    )
    writer.begin(first, observation_timestamp=10.0)
    writer.write_step(
        action=2,
        reward=1.0,
        reward_components={"floor_reward": 1.0},
        next_observation=second,
        terminated=False,
        truncated=False,
        events=[{"type": "floor_descended"}],
        timing=timing(10.0),
        target_platform_id=7,
        target_platform_kind="normal",
        target_signed_offset=12.0,
    )
    writer.close()

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["step"] == 0
    assert row["observation"] == first.tolist()
    assert row["next_observation"] == pytest.approx(second.tolist())
    assert row["policy_source"] == "baseline"


def test_writer_refuses_overwrite_reward_mismatch_and_post_terminal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "transitions.jsonl"
    obs = np.zeros(OBSERVATION_DIM, dtype=np.float32)
    writer = TransitionJsonlWriter(path, policy_source="human")
    writer.begin(obs, observation_timestamp=1.0)
    with pytest.raises(ValueError, match="reward_components"):
        writer.write_step(
            action=0,
            reward=1.0,
            reward_components={"step_penalty": 0.0},
            next_observation=obs,
            terminated=False,
            truncated=False,
            events=[],
            timing=timing(1.0),
        )
    writer.write_step(
        action=0,
        reward=0.0,
        reward_components={"step_penalty": 0.0},
        next_observation=obs,
        terminated=True,
        truncated=False,
        events=[],
        timing=timing(1.0),
    )
    with pytest.raises(RuntimeError, match="結束"):
        writer.write_step(
            action=0,
            reward=0.0,
            reward_components={"step_penalty": 0.0},
            next_observation=obs,
            terminated=False,
            truncated=False,
            events=[],
            timing=timing(1.1),
        )
    writer.close()
    with pytest.raises(FileExistsError):
        TransitionJsonlWriter(path, policy_source="human")
