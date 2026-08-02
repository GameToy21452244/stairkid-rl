from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402
import numpy as np
import torch

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import TeacherObservable
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.behavior_cloning import BehaviorCloningMLP


def failure_category(env: ShaftEnv, teacher_action: int, bc_action: int) -> str:
    player = env.last_observation.player or {}
    x = float(player.get("center_x", env.config.width / 2))
    vx = float(player.get("velocity_x", 0.0))
    margin = env.config.player_width * 1.5
    if x <= margin or x >= env.config.width - margin:
        return "wall_collision"
    if teacher_action == 0 and bc_action in {1, 2} and abs(vx) > 60:
        return "brake_too_late"
    if teacher_action in {1, 2} and bc_action in {1, 2}:
        return "wrong_target"
    return "missed_platform_risk"


def main() -> int:
    model = BehaviorCloningMLP()
    model.load_state_dict(
        torch.load(
            "artifacts/bc0_hard_v0_model.pt",
            map_location="cpu",
            weights_only=True,
        )
    )
    model.eval()
    corrections = []
    categories = Counter()
    rollout = []
    config = ShaftEnvConfig(distribution="easy", fps=10, max_episode_steps=600)
    for seed in range(300, 320):
        env = ShaftEnv(config=config)
        teacher = TeacherObservable(verified=True)
        observation, _info = env.reset(seed=seed)
        disagreements = 0
        try:
            for step in range(config.max_episode_steps):
                with torch.no_grad():
                    probabilities = torch.softmax(
                        model(
                            torch.as_tensor(
                                observation, dtype=torch.float32
                            ).unsqueeze(0)
                        )[0],
                        dim=0,
                    ).numpy()
                bc_action = int(np.argmax(probabilities))
                decision = teacher.choose(env.last_observation)
                teacher_action = int(decision.action)
                if bc_action != teacher_action:
                    category = failure_category(
                        env, teacher_action, bc_action
                    )
                    categories[category] += 1
                    disagreements += 1
                    corrections.append(
                        {
                            "schema_version": "ns-shaft-correction-v1",
                            "episode_id": f"dagger0-seed-{seed:04d}",
                            "seed": seed,
                            "split": "train",
                            "platform_sequence_id": f"dagger0-seed-{seed:04d}",
                            "step": step,
                            "observation": observation.astype(float).tolist(),
                            "action": teacher_action,
                            "soft_target": list(decision.action_distribution),
                            "teacher_confidence": decision.confidence,
                            "candidate_action_values": list(
                                decision.candidate_action_values
                            ),
                            "teacher_type": "teacher_observable",
                            "verified": True,
                            "policy_source": "corrected",
                            "learner_action": bc_action,
                            "learner_action_distribution": probabilities.tolist(),
                            "failure_category": category,
                            "environment_version": config.environment_version,
                            "observation_schema_version": (
                                "stair-observation-v3-268"
                            ),
                        }
                    )
                observation, _reward, terminated, truncated, info = env.step(
                    bc_action
                )
                if terminated or truncated:
                    rollout.append(
                        {
                            "seed": seed,
                            "floors": env.simulator.deepest_floor,
                            "steps": step + 1,
                            "terminal_reason": info["terminal_reason"],
                            "corrections": disagreements,
                        }
                    )
                    break
        finally:
            env.close()

    correction_path = Path("artifacts/dagger0_corrections.jsonl")
    with correction_path.open("w", encoding="utf-8") as stream:
        for row in corrections:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
    combined_path = Path("artifacts/teacher_dataset_dagger0.jsonl")
    with combined_path.open("w", encoding="utf-8") as target:
        target.write(
            Path("artifacts/teacher_dataset_v0.jsonl").read_text(
                encoding="utf-8"
            )
        )
        target.write(correction_path.read_text(encoding="utf-8"))
    summary = {
        "aggregation_seeds": list(range(300, 320)),
        "correction_records": len(corrections),
        "failure_categories": dict(categories),
        "mean_corrections_per_episode": float(
            np.mean([item["corrections"] for item in rollout])
        ),
        "rollout": rollout,
        "source_model": "bc0_hard_v0_model.pt",
        "combined_dataset": str(combined_path),
    }
    Path("artifacts/dagger0_collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
