import os
from pathlib import Path

import numpy as np
import pytest

from stair_agent.rl_evaluation import (
    evaluate_policy,
    resolve_evaluation_model,
)


class MockModel:
    def predict(self, observation, *, deterministic):
        assert deterministic
        assert observation.shape == (4,)
        return np.int64(1), None


class TwoStepEvaluationEnv:
    def __init__(self) -> None:
        self.reset_count = 0
        self.episode_step = 0
        self.actions: list[int] = []

    def reset(self):
        self.reset_count += 1
        self.episode_step = 0
        return np.zeros(4, dtype=np.float32), {"phase": "playing"}

    def step(self, action):
        self.actions.append(int(action))
        self.episode_step += 1
        terminated = self.episode_step == 2
        return (
            np.zeros(4, dtype=np.float32),
            1.0,
            terminated,
            False,
            {"phase": "dialog" if terminated else "playing"},
        )


def test_evaluation_stops_without_reset_after_final_episode() -> None:
    env = TwoStepEvaluationEnv()

    result = evaluate_policy(
        env,
        MockModel(),
        max_steps=20,
        max_episodes=2,
        max_seconds=30.0,
    )

    assert result.stop_reason == "episode_limit"
    assert result.steps == 4
    assert result.completed_episodes == 2
    assert result.episode_lengths == [2, 2]
    assert result.episode_rewards == [2.0, 2.0]
    assert env.reset_count == 2


def test_evaluation_step_limit_never_sends_an_extra_action() -> None:
    env = TwoStepEvaluationEnv()

    result = evaluate_policy(
        env,
        MockModel(),
        max_steps=3,
        max_episodes=10,
        max_seconds=30.0,
    )

    assert result.stop_reason == "step_limit"
    assert result.steps == 3
    assert len(env.actions) == 3
    assert env.reset_count == 2


def test_evaluation_time_limit_stops_before_next_action() -> None:
    env = TwoStepEvaluationEnv()
    moments = iter([0.0, 0.0, 31.0, 31.0])

    result = evaluate_policy(
        env,
        MockModel(),
        max_steps=20,
        max_episodes=10,
        max_seconds=30.0,
        clock=lambda: next(moments),
    )

    assert result.stop_reason == "time_limit"
    assert result.steps == 1
    assert len(env.actions) == 1


def test_resolve_evaluation_model_is_confined_to_models(
    tmp_path: Path,
) -> None:
    older = tmp_path / "models" / "ppo" / "old" / "final_model.zip"
    newer = tmp_path / "models" / "ppo" / "new" / "final_model.zip"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

    assert resolve_evaluation_model(tmp_path, None) == newer.resolve()
    assert (
        resolve_evaluation_model(
            tmp_path,
            "models/ppo/old/final_model.zip",
        )
        == older.resolve()
    )

    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"unsafe")
    with pytest.raises(ValueError, match="models"):
        resolve_evaluation_model(tmp_path, str(outside))
    with pytest.raises(ValueError, match=r"\.zip"):
        resolve_evaluation_model(tmp_path, "models/ppo/old/not_zip.pt")
