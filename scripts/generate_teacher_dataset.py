from __future__ import annotations

import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.data.schema import OBSERVATION_SCHEMA_VERSION
from stair_agent.data.teacher_dataset import (
    TEACHER_SCHEMA_VERSION,
    TeacherRecord,
    write_teacher_jsonl,
)
from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import TeacherObservable
from stair_agent.simulator.state import ShaftEnvConfig


def split_for_seed(seed: int) -> str:
    if seed < 40:
        return "train"
    if seed < 50:
        return "validation"
    return "test"


def main() -> int:
    records = []
    config = ShaftEnvConfig(distribution="easy", fps=10, max_episode_steps=300)
    for seed in range(60):
        env = ShaftEnv(config=config)
        teacher = TeacherObservable(verified=True)
        observation, _info = env.reset(seed=seed)
        episode_id = f"sim-v02-seed-{seed:04d}"
        split = split_for_seed(seed)
        try:
            for step in range(config.max_episode_steps):
                decision = teacher.choose(env.last_observation)
                next_observation, reward, terminated, truncated, info = env.step(
                    int(decision.action)
                )
                records.append(
                    TeacherRecord(
                        schema_version=TEACHER_SCHEMA_VERSION,
                        episode_id=episode_id,
                        seed=seed,
                        split=split,
                        platform_sequence_id=f"easy-seed-{seed:04d}",
                        step=step,
                        observation=observation.astype(float).tolist(),
                        action=int(decision.action),
                        soft_target=list(decision.action_distribution),
                        teacher_confidence=decision.confidence,
                        candidate_action_values=list(decision.candidate_action_values),
                        teacher_type=decision.teacher_type,
                        verified=decision.verified,
                        target_platform_id=decision.target_platform_id,
                        target_platform_kind=decision.target_platform_kind,
                        next_observation=next_observation.astype(float).tolist(),
                        reward=float(reward),
                        events=list(info["events"]),
                        terminated=terminated,
                        truncated=truncated,
                        environment_version=config.environment_version,
                        observation_schema_version=OBSERVATION_SCHEMA_VERSION,
                        failure_reason=info["failure_reason"],
                    )
                )
                observation = next_observation
                if env.simulator.deepest_floor >= 10 or terminated or truncated:
                    break
        finally:
            env.close()
    summary = write_teacher_jsonl(records, "artifacts/teacher_dataset_v0.jsonl")
    summary.update(
        {
            "environment_version": config.environment_version,
            "control_frequency_hz": config.fps,
            "physics_frequency_hz": config.physics_hz,
            "teacher_type": "teacher_observable",
            "verified": True,
        }
    )
    Path("artifacts/teacher_dataset_v0_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
