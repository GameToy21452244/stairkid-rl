from __future__ import annotations

import argparse
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402
import numpy as np
import torch

from stair_agent.data.schema import OBSERVATION_SCHEMA_VERSION
from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import TeacherObservable
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.behavior_cloning import BehaviorCloningMLP
from stair_agent.training.dagger_corrections import (
    classify_disagreement,
    terminal_aware_category,
)


def spike_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        max_episode_steps=600,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def load_selected_models(archive_path: Path):
    loaded = []
    with zipfile.ZipFile(archive_path) as archive:
        for initialization_seed in (0, 1, 2):
            summary_name = (
                f"spike_bc0_colab_seed_{initialization_seed}_smoke_summary.json"
            )
            summary = json.loads(archive.read(summary_name))
            if not summary["gate"]["passed"]:
                raise RuntimeError(
                    f"source BC0 seed {initialization_seed} 未通過 final gate。"
                )
            model_name = f"spike_bc0_colab_seed_{initialization_seed}_model.pt"
            state = torch.load(
                io.BytesIO(archive.read(model_name)),
                map_location="cpu",
                weights_only=True,
            )
            model = BehaviorCloningMLP()
            model.load_state_dict(state)
            loaded.append(
                (
                    initialization_seed,
                    int(summary["selected_epoch"]),
                    model.eval(),
                )
            )
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-archive",
        type=Path,
        default=Path("../20260730T205104Z_spike_bc0.zip"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/spike_dagger0_corrections.jsonl"),
    )
    parser.add_argument("--aggregation-seed-start", type=int, default=1300)
    parser.add_argument("--episodes-per-model", type=int, default=20)
    args = parser.parse_args()
    if args.episodes_per_model <= 0:
        parser.error("--episodes-per-model 必須大於 0。")
    if not args.source_archive.is_file():
        parser.error(f"找不到 source archive：{args.source_archive}")

    config = spike_config()
    corrections = []
    categories = Counter()
    actions = Counter()
    terminals = Counter()
    rollout = []
    source_models = load_selected_models(args.source_archive)

    for source_index, (initialization_seed, selected_epoch, model) in enumerate(
        source_models
    ):
        start = args.aggregation_seed_start + source_index * args.episodes_per_model
        for seed in range(start, start + args.episodes_per_model):
            env = ShaftEnv(config=config)
            teacher = TeacherObservable(verified=True)
            observation, _info = env.reset(seed=seed)
            episode_rows = []
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
                    learner_action = int(np.argmax(probabilities))
                    decision = teacher.choose(env.last_observation)
                    teacher_action = int(decision.action)
                    if learner_action != teacher_action:
                        category = classify_disagreement(
                            player=env.last_observation.player,
                            visible_platform_kinds=(
                                item.get("kind")
                                for item in env.last_observation.platforms
                            ),
                            width=env.config.width,
                            player_width=env.config.player_width,
                            teacher_action=teacher_action,
                            learner_action=learner_action,
                            learner_confidence=float(
                                probabilities[learner_action]
                            ),
                        )
                        row = {
                            "schema_version": "ns-shaft-correction-v1",
                            "episode_id": (
                                f"spike-dagger0-source-{initialization_seed}-seed-{seed}"
                            ),
                            "seed": seed,
                            "split": "train",
                            "platform_sequence_id": f"spike-v0-seed-{seed}",
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
                            "learner_action": learner_action,
                            "learner_action_distribution": probabilities.tolist(),
                            "learner_confidence": float(
                                probabilities[learner_action]
                            ),
                            "failure_category": category,
                            "source_initialization_seed": initialization_seed,
                            "source_selected_epoch": selected_epoch,
                            "player_motion": (
                                env.last_observation.player or {}
                            ).get("motion"),
                            "visible_platform_kinds": [
                                item.get("kind")
                                for item in env.last_observation.platforms
                            ],
                            "health_segments": env.simulator.health_segments,
                            "environment_version": (
                                config.effective_environment_version
                            ),
                            "observation_schema_version": (
                                OBSERVATION_SCHEMA_VERSION
                            ),
                        }
                        episode_rows.append(row)
                    observation, _reward, terminated, truncated, info = env.step(
                        learner_action
                    )
                    if terminated or truncated:
                        terminal_reason = str(info["terminal_reason"])
                        terminals[terminal_reason] += 1
                        for row in episode_rows:
                            distance = step - int(row["step"])
                            row["terminal_reason"] = terminal_reason
                            row["steps_to_terminal"] = distance
                            row["failure_category"] = terminal_aware_category(
                                row["failure_category"],
                                terminal_reason=terminal_reason,
                                steps_to_terminal=distance,
                            )
                            categories[row["failure_category"]] += 1
                            actions[int(row["action"])] += 1
                        corrections.extend(episode_rows)
                        rollout.append(
                            {
                                "source_initialization_seed": initialization_seed,
                                "selected_epoch": selected_epoch,
                                "environment_seed": seed,
                                "floors": env.simulator.deepest_floor,
                                "steps": step + 1,
                                "terminal_reason": terminal_reason,
                                "corrections": len(episode_rows),
                            }
                        )
                        break
            finally:
                env.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in corrections:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
    summary = {
        "protocol": "spike-dagger0-bounded-v0",
        "source_archive": str(args.source_archive),
        "source_models": [
            {"initialization_seed": seed, "selected_epoch": epoch}
            for seed, epoch, _model in source_models
        ],
        "aggregation_seeds": sorted({item["environment_seed"] for item in rollout}),
        "episodes": len(rollout),
        "correction_records": len(corrections),
        "teacher_action_counts": {
            str(action): actions[action] for action in range(3)
        },
        "failure_categories": dict(categories),
        "terminal_reasons": dict(terminals),
        "mean_corrections_per_episode": float(
            np.mean([item["corrections"] for item in rollout])
        ),
        "output": str(args.output),
        "rollout": rollout,
    }
    summary_path = args.output.with_name(
        "spike_dagger0_collection_summary.json"
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "rollout"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
