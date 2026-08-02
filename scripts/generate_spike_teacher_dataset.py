from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.data.schema import OBSERVATION_SCHEMA_VERSION
from stair_agent.data.teacher_dataset import (
    TEACHER_SCHEMA_VERSION,
    TeacherRecord,
    assess_spike_teacher_dataset,
    write_teacher_jsonl,
)
from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import (
    TEACHER_POLICY_VERSION,
    TeacherObservable,
)
from stair_agent.simulator.state import ShaftEnvConfig


SEED_START = 1000
SEED_COUNT = 60


def split_for_index(index: int, count: int = SEED_COUNT) -> str:
    train_end = count * 2 // 3
    validation_end = count * 5 // 6
    if index < train_end:
        return "train"
    if index < validation_end:
        return "validation"
    return "test"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=SEED_START)
    parser.add_argument("--seed-count", type=int, default=SEED_COUNT)
    parser.add_argument(
        "--dataset-id",
        default="spike_teacher_dataset_v0",
    )
    parser.add_argument("--episode-prefix", default="spike-v0")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--teacher-gate", type=Path)
    args = parser.parse_args()
    if args.seed_count < 6:
        parser.error("--seed-count 至少為 6，才能建立三個非空 split。")
    if not args.dataset_id.replace("_", "").replace("-", "").isalnum():
        parser.error("--dataset-id 只允許英數字、底線與連字號。")

    gate_path = Path("artifacts/spike_curriculum_v0_gate.json")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if not gate.get("passed"):
        raise RuntimeError(
            "spike curriculum gate 未通過，拒絕生成 Teacher Dataset。"
        )
    teacher_gate = None
    if args.teacher_gate is not None:
        teacher_gate = json.loads(
            args.teacher_gate.read_text(encoding="utf-8")
        )
        if not teacher_gate.get("gate", {}).get("passed"):
            raise RuntimeError(
                "Teacher reliability gate 未通過，拒絕生成新版資料。"
            )
    elif args.dataset_id != "spike_teacher_dataset_v0":
        raise RuntimeError(
            "新版 Teacher Dataset 必須提供 --teacher-gate。"
        )

    dataset_path = args.output or Path(
        f"artifacts/{args.dataset_id}.jsonl"
    )
    summary_path = args.summary_output or Path(
        f"artifacts/{args.dataset_id}_summary.json"
    )
    existing = [
        str(path) for path in (dataset_path, summary_path) if path.exists()
    ]
    if existing:
        raise FileExistsError(
            "拒絕覆寫既有 Teacher Dataset artifact："
            + ", ".join(existing)
        )

    records = []
    event_counts: Counter[str] = Counter()
    target_kind_counts: Counter[str] = Counter()
    visible_kind_counts: Counter[str] = Counter()
    spike_visible_by_split: Counter[str] = Counter()
    teacher_reason_counts: Counter[str] = Counter()
    terminal_reasons: Counter[str] = Counter()
    episodes_with_spike_visible: set[str] = set()
    minimum_health = 12
    all_teacher_verified = True
    config = ShaftEnvConfig(
        distribution="easy",
        fps=10,
        max_episode_steps=300,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )
    for index in range(args.seed_count):
        seed = args.seed_start + index
        env = ShaftEnv(config=config)
        teacher = TeacherObservable(verified=True)
        observation, _info = env.reset(seed=seed)
        episode_id = f"{args.episode_prefix}-seed-{seed:04d}"
        split = split_for_index(index, args.seed_count)
        try:
            for step in range(config.max_episode_steps):
                visible_kinds = [
                    str(platform.get("kind", ""))
                    for platform in env.last_observation.platforms
                ]
                visible_kind_counts.update(visible_kinds)
                if "spikes" in visible_kinds:
                    spike_visible_by_split[split] += 1
                    episodes_with_spike_visible.add(episode_id)
                health_before_action = int(
                    (env.last_observation.health or {}).get(
                        "segments", config.initial_health_segments
                    )
                )
                decision = teacher.choose(env.last_observation)
                teacher_reason_counts[decision.reason] += 1
                all_teacher_verified &= decision.verified
                next_observation, reward, terminated, truncated, info = (
                    env.step(int(decision.action))
                )
                event_counts.update(info["events"])
                target_kind_counts[
                    decision.target_platform_kind or "none"
                ] += 1
                minimum_health = min(
                    minimum_health, int(info["health_segments"])
                )
                records.append(
                    TeacherRecord(
                        schema_version=TEACHER_SCHEMA_VERSION,
                        episode_id=episode_id,
                        seed=seed,
                        split=split,
                        platform_sequence_id=(
                            f"{args.episode_prefix}-seed-{seed:04d}"
                        ),
                        step=step,
                        observation=observation.astype(float).tolist(),
                        action=int(decision.action),
                        soft_target=list(
                            decision.action_distribution
                        ),
                        teacher_confidence=decision.confidence,
                        candidate_action_values=list(
                            decision.candidate_action_values
                        ),
                        teacher_type=decision.teacher_type,
                        verified=decision.verified,
                        target_platform_id=decision.target_platform_id,
                        target_platform_kind=(
                            decision.target_platform_kind
                        ),
                        next_observation=(
                            next_observation.astype(float).tolist()
                        ),
                        reward=float(reward),
                        events=list(info["events"]),
                        terminated=terminated,
                        truncated=truncated,
                        environment_version=(
                            config.effective_environment_version
                        ),
                        observation_schema_version=(
                            OBSERVATION_SCHEMA_VERSION
                        ),
                        failure_reason=info["failure_reason"],
                        visible_platform_kinds=visible_kinds,
                        health_segments=health_before_action,
                        teacher_policy_version=(
                            decision.policy_version
                        ),
                        teacher_reason=decision.reason,
                    )
                )
                observation = next_observation
                if (
                    env.simulator.deepest_floor >= 10
                    or terminated
                    or truncated
                ):
                    if terminated or truncated:
                        terminal_reasons[
                            str(info["terminal_reason"])
                        ] += 1
                    else:
                        terminal_reasons["target_reached"] += 1
                    break
        finally:
            env.close()

    summary = write_teacher_jsonl(records, dataset_path)
    summary.update(
        {
            "environment_version": (
                config.effective_environment_version
            ),
            "control_frequency_hz": config.fps,
            "physics_frequency_hz": config.physics_hz,
            "teacher_type": "teacher_observable",
            "verified": True,
            "all_teacher_verified": all_teacher_verified,
            "teacher_policy_version": TEACHER_POLICY_VERSION,
            "dataset_id": args.dataset_id,
            "seed_range": [
                args.seed_start,
                args.seed_start + args.seed_count - 1,
            ],
            "gate_artifact": str(gate_path),
            "teacher_gate_artifact": (
                None
                if args.teacher_gate is None
                else str(args.teacher_gate)
            ),
            "curriculum": {
                "spike_proposal_probability": (
                    config.spike_spawn_probability
                ),
                "initial_safe_normal_platforms": (
                    config.initial_safe_normal_platforms
                ),
                "minimum_normal_platforms_between_spikes": (
                    config.minimum_normal_platforms_between_spikes
                ),
            },
            "event_counts": dict(event_counts),
            "target_kind_counts": dict(target_kind_counts),
            "teacher_reason_counts": dict(teacher_reason_counts),
            "terminal_reasons": dict(terminal_reasons),
            "visible_kind_counts": dict(visible_kind_counts),
            "spike_visible_records_by_split": dict(
                spike_visible_by_split
            ),
            "episodes_with_spike_visible": len(
                episodes_with_spike_visible
            ),
            "minimum_observed_health": minimum_health,
        }
    )
    summary["dataset_gate"] = assess_spike_teacher_dataset(
        summary,
        expected_episodes=args.seed_count,
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["dataset_gate"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
