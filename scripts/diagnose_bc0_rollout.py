from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import _common  # noqa: F401,E402
import numpy as np
import torch

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import TeacherObservable
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.behavior_cloning import BehaviorCloningMLP


def main() -> int:
    model = BehaviorCloningMLP()
    model.load_state_dict(
        torch.load("artifacts/bc0_model.pt", map_location="cpu", weights_only=True)
    )
    model.eval()
    confusion = np.zeros((3, 3), dtype=np.int64)
    confidence_by_pair: dict[str, list[float]] = defaultdict(list)
    disagreement_motion = Counter()
    disagreement_floor = Counter()
    near_terminal = Counter()
    all_actions = Counter()
    disagreement_examples = []
    episode_summaries = []

    for seed in range(100, 120):
        env = ShaftEnv(
            config=ShaftEnvConfig(
                distribution="easy", fps=10, max_episode_steps=600
            )
        )
        teacher = TeacherObservable(verified=True)
        observation, _info = env.reset(seed=seed)
        history = []
        try:
            for step in range(600):
                with torch.no_grad():
                    logits = model(
                        torch.as_tensor(observation, dtype=torch.float32).unsqueeze(0)
                    )[0]
                    probabilities = torch.softmax(logits, dim=0).numpy()
                bc_action = int(np.argmax(probabilities))
                teacher_decision = teacher.choose(env.last_observation)
                teacher_action = int(teacher_decision.action)
                confusion[teacher_action, bc_action] += 1
                pair = f"{teacher_action}->{bc_action}"
                confidence_by_pair[pair].append(float(probabilities[bc_action]))
                all_actions[bc_action] += 1
                disagreed = bc_action != teacher_action
                if disagreed:
                    motion = str((env.last_observation.player or {}).get("motion"))
                    disagreement_motion[motion] += 1
                    disagreement_floor[env.simulator.deepest_floor] += 1
                    if len(disagreement_examples) < 100:
                        player = env.last_observation.player or {}
                        disagreement_examples.append(
                            {
                                "seed": seed,
                                "step": step,
                                "floor": env.simulator.deepest_floor,
                                "motion": motion,
                                "player_x": player.get("center_x"),
                                "player_y": player.get("center_y"),
                                "player_vx": player.get("velocity_x"),
                                "player_vy": player.get("velocity_y"),
                                "teacher_action": teacher_action,
                                "bc_action": bc_action,
                                "bc_probabilities": probabilities.tolist(),
                                "target_platform_id": teacher_decision.target_platform_id,
                            }
                        )
                observation, _reward, terminated, truncated, info = env.step(bc_action)
                history.append(
                    {
                        "teacher": teacher_action,
                        "bc": bc_action,
                        "disagreed": disagreed,
                    }
                )
                if terminated or truncated:
                    for distance, item in enumerate(reversed(history[-20:]), start=1):
                        if item["disagreed"]:
                            near_terminal[f"last_{distance:02d}_steps"] += 1
                    episode_summaries.append(
                        {
                            "seed": seed,
                            "floors": env.simulator.deepest_floor,
                            "length": step + 1,
                            "terminal_reason": info["terminal_reason"],
                            "disagreements": sum(item["disagreed"] for item in history),
                            "last20_disagreements": sum(
                                item["disagreed"] for item in history[-20:]
                            ),
                        }
                    )
                    break
        finally:
            env.close()

    total = int(confusion.sum())
    disagreement = int(total - np.trace(confusion))
    payload = {
        "seeds": list(range(100, 120)),
        "teacher_vs_bc_confusion": confusion.tolist(),
        "total_steps": total,
        "disagreement_count": disagreement,
        "disagreement_rate": disagreement / max(1, total),
        "bc_action_counts": {str(i): all_actions[i] for i in range(3)},
        "disagreement_by_motion": dict(disagreement_motion),
        "disagreement_by_floor": {
            str(key): value for key, value in sorted(disagreement_floor.items())
        },
        "mean_bc_confidence_by_teacher_to_bc_pair": {
            pair: float(np.mean(values))
            for pair, values in sorted(confidence_by_pair.items())
        },
        "near_terminal_disagreement_positions": dict(near_terminal),
        "episodes": episode_summaries,
        "examples": disagreement_examples,
    }
    target = Path("artifacts/bc0_rollout_diagnostic.json")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "confusion": payload["teacher_vs_bc_confusion"],
                "disagreement_rate": payload["disagreement_rate"],
                "motion": payload["disagreement_by_motion"],
                "episode_mean_disagreements": float(
                    np.mean([item["disagreements"] for item in episode_summaries])
                ),
                "episode_mean_last20_disagreements": float(
                    np.mean([item["last20_disagreements"] for item in episode_summaries])
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
