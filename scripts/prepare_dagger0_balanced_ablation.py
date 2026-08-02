from __future__ import annotations

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
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row, cluster in zip(rows, labels):
        if int(row["action"]) == action:
            groups[(int(cluster), row["failure_category"])].append(row)
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
    teacher_rows = read_jsonl(Path("artifacts/teacher_dataset_v0.jsonl"))
    train_rows = [row for row in teacher_rows if row["split"] == "train"]
    corrections = read_jsonl(Path("artifacts/dagger0_corrections.jsonl"))
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
    selected_actions = Counter(int(row["action"]) for row in selected)
    selected_categories = Counter(row["failure_category"] for row in selected)
    selected_episodes = Counter(row["episode_id"] for row in selected)
    selected_hashes = {
        json.dumps(row["observation"], separators=(",", ":"))
        for row in selected
    }
    if len(selected_hashes) != len(selected):
        raise RuntimeError("balanced corrections 含重複 observation。")

    combined = Path("artifacts/teacher_dataset_dagger0_balanced.jsonl")
    with combined.open("w", encoding="utf-8") as stream:
        for row in teacher_rows:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
        for row in selected:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
    summary = {
        "design_frozen_before_training": True,
        "base_train_records": len(train_rows),
        "correction_cap_ratio": 0.25,
        "selected_corrections": len(selected),
        "selected_to_base_ratio": len(selected) / len(train_rows),
        "target_action_quotas": {
            str(action): quotas[action] for action in range(3)
        },
        "selected_action_counts": {
            str(action): selected_actions[action] for action in range(3)
        },
        "selected_failure_categories": dict(selected_categories),
        "selected_episodes": len(selected_episodes),
        "largest_episode_records": max(selected_episodes.values()),
        "largest_episode_share": (
            max(selected_episodes.values()) / len(selected)
        ),
        "state_clusters": 12,
        "sampling": "round_robin(cluster,failure_category) within action",
        "random_seed": 20260731,
        "output_dataset": str(combined),
    }
    Path("artifacts/dagger0_balanced_design.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
