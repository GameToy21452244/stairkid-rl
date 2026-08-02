from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np

from audit_dagger0_corrections import kmeans, read_jsonl


def round_robin_sample(
    rows: list[dict],
    labels: np.ndarray,
    *,
    action: int,
    quota: int,
    rng: np.random.Generator,
) -> list[dict]:
    groups: dict[tuple[int, str, int], list[dict]] = defaultdict(list)
    for row, cluster in zip(rows, labels):
        if int(row["action"]) == action:
            groups[
                (
                    int(cluster),
                    row["failure_category"],
                    int(row["source_initialization_seed"]),
                )
            ].append(row)
    queues = []
    for key in sorted(groups):
        values = groups[key]
        rng.shuffle(values)
        queues.append(deque(values))
    selected = []
    while queues and len(selected) < quota:
        remaining = []
        for queue in queues:
            if queue and len(selected) < quota:
                selected.append(queue.popleft())
            if queue:
                remaining.append(queue)
        queues = remaining
    if len(selected) != quota:
        raise RuntimeError(f"action {action} quota {quota} 無法滿足。")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--teacher-dataset",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_v0.jsonl"),
    )
    parser.add_argument(
        "--corrections",
        type=Path,
        default=Path("artifacts/spike_dagger0_corrections.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_dagger0_balanced.jsonl"),
    )
    args = parser.parse_args()
    teacher_rows = read_jsonl(args.teacher_dataset)
    train_rows = [row for row in teacher_rows if row["split"] == "train"]
    corrections = read_jsonl(args.corrections)
    if not corrections:
        raise RuntimeError("沒有可供 balanced sampling 的 corrections。")
    observations = np.asarray(
        [row["observation"] for row in corrections], dtype=np.float32
    )
    labels = kmeans(observations, clusters=12)
    base_actions = Counter(int(row["action"]) for row in train_rows)
    correction_cap = round(len(train_rows) * 0.25)
    quotas = {
        action: round(correction_cap * base_actions[action] / len(train_rows))
        for action in range(3)
    }
    quotas[0] += correction_cap - sum(quotas.values())
    available = Counter(int(row["action"]) for row in corrections)
    for action, quota in quotas.items():
        if available[action] < quota:
            raise RuntimeError(
                f"action {action} corrections 不足：{available[action]} < {quota}。"
            )

    rng = np.random.default_rng(20260731)
    selected = []
    for action in range(3):
        selected.extend(
            round_robin_sample(
                corrections,
                labels,
                action=action,
                quota=quotas[action],
                rng=rng,
            )
        )
    rng.shuffle(selected)
    observation_hashes = [
        hashlib.sha256(
            np.asarray(row["observation"], dtype=np.float32).tobytes()
        ).hexdigest()
        for row in selected
    ]
    if len(set(observation_hashes)) != len(observation_hashes):
        raise RuntimeError("balanced corrections 含重複 observation。")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in [*teacher_rows, *selected]:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")

    selected_actions = Counter(int(row["action"]) for row in selected)
    selected_categories = Counter(row["failure_category"] for row in selected)
    selected_sources = Counter(
        int(row["source_initialization_seed"]) for row in selected
    )
    selected_episodes = Counter(row["episode_id"] for row in selected)
    selected_spike_visible = sum(
        "spikes" in row.get("visible_platform_kinds", []) for row in selected
    )
    selected_near_terminal = sum(
        int(row.get("steps_to_terminal", 9999)) < 20 for row in selected
    )
    summary = {
        "protocol": "spike-dagger0-balanced-v0",
        "design_frozen_before_training": True,
        "base_train_records": len(train_rows),
        "correction_cap_ratio": 0.25,
        "available_corrections": len(corrections),
        "selected_corrections": len(selected),
        "selected_to_base_ratio": len(selected) / len(train_rows),
        "target_action_quotas": {
            str(action): quotas[action] for action in range(3)
        },
        "selected_action_counts": {
            str(action): selected_actions[action] for action in range(3)
        },
        "selected_failure_categories": dict(selected_categories),
        "selected_source_models": {
            str(seed): selected_sources[seed] for seed in range(3)
        },
        "selected_episodes": len(selected_episodes),
        "largest_episode_records": max(selected_episodes.values()),
        "largest_episode_share": max(selected_episodes.values()) / len(selected),
        "selected_spike_visible": selected_spike_visible,
        "selected_near_terminal": selected_near_terminal,
        "state_clusters": 12,
        "sampling": (
            "round_robin(cluster,failure_category,source_model) within action"
        ),
        "random_seed": 20260731,
        "output_dataset": str(args.output),
    }
    summary_path = args.output.with_name("spike_dagger0_balanced_design.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
