import json
from pathlib import Path

import numpy as np
import pytest

from stair_agent.config import EnvironmentConfig
from stair_agent.observation import GameObservation
from stair_agent.trajectory import RewardAuditor, TrajectoryJsonlWriter


def observation(*, phase="playing", events=None, health=12):
    return GameObservation(
        timestamp=10.0,
        phase=phase,
        player=None,
        health={"segments": health, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=events or [],
    )


def test_reward_auditor_accumulates_events_and_terminal_reason() -> None:
    auditor = RewardAuditor(
        EnvironmentConfig(
            floor_reward=1.0,
            damage_penalty_per_segment=0.2,
            death_penalty=5.0,
        )
    )

    first = auditor.evaluate(
        observation(
            events=[
                {"type": "floor_descended", "health_delta": 1},
                {"type": "damage", "health_delta": -4},
            ],
            health=8,
        )
    )
    final = auditor.evaluate(observation(phase="dialog", health=0))

    assert first.reward == pytest.approx(0.2)
    assert not first.terminated
    assert final.reward == pytest.approx(-5.0)
    assert final.terminated
    assert not final.truncated
    assert auditor.summary()["steps"] == 2
    assert auditor.summary()["total_reward"] == pytest.approx(-4.8)
    assert auditor.summary()["event_counts"] == {
        "damage": 1,
        "floor_descended": 1,
    }
    assert auditor.summary()["end_reason"] == "dialog"


def test_unknown_phase_is_truncated_not_death() -> None:
    auditor = RewardAuditor(EnvironmentConfig(death_penalty=5.0))

    result = auditor.evaluate(observation(phase="unknown"))

    assert result.reward == 0.0
    assert not result.terminated
    assert result.truncated
    assert auditor.summary()["end_reason"] == "unknown"


def test_trajectory_writer_writes_jsonl_and_summary(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    auditor = RewardAuditor(EnvironmentConfig())
    result = auditor.evaluate(
        observation(events=[{"type": "floor_descended"}])
    )
    writer = TrajectoryJsonlWriter(path)

    writer.write(
        step=1,
        action="manual",
        observation=observation(events=[{"type": "floor_descended"}]),
        features=np.zeros(64, dtype=np.float32),
        result=result,
        cumulative_reward=auditor.total_reward,
        policy_decision={"reason": "test"},
        decision_observation=observation(health=9),
    )
    writer.close(auditor.summary())

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    summary = json.loads(
        path.with_suffix(".summary.json").read_text(encoding="utf-8")
    )
    assert rows[0]["step"] == 1
    assert rows[0]["action"] == "manual"
    assert rows[0]["reward"] == 1.0
    assert len(rows[0]["features"]) == 64
    assert rows[0]["observation"]["phase"] == "playing"
    assert rows[0]["policy_decision"]["reason"] == "test"
    assert rows[0]["decision_observation"]["health"]["segments"] == 9
    assert summary["steps"] == 1
    assert summary["event_counts"] == {"floor_descended": 1}


def test_trajectory_writer_refuses_to_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        TrajectoryJsonlWriter(path)


def test_trajectory_writer_refuses_to_overwrite_summary(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.with_suffix(".summary.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError):
        TrajectoryJsonlWriter(path)
