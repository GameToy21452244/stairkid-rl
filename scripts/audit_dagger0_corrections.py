from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def kmeans(values: np.ndarray, clusters: int, seed: int = 20260731) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centers = values[rng.choice(len(values), size=clusters, replace=False)].copy()
    labels = np.zeros(len(values), dtype=np.int64)
    for _ in range(30):
        distances = (
            (values[:, None, :] - centers[None, :, :]) ** 2
        ).mean(axis=2)
        updated_labels = distances.argmin(axis=1)
        if np.array_equal(updated_labels, labels):
            break
        labels = updated_labels
        for cluster in range(clusters):
            members = values[labels == cluster]
            if len(members):
                centers[cluster] = members.mean(axis=0)
    return labels


def main() -> int:
    corrections = read_jsonl(Path("artifacts/dagger0_corrections.jsonl"))
    teacher = [
        row
        for row in read_jsonl(Path("artifacts/teacher_dataset_v0.jsonl"))
        if row["split"] == "train"
    ]
    observations = np.asarray(
        [row["observation"] for row in corrections], dtype=np.float32
    )
    labels = kmeans(observations, clusters=12)

    exact = Counter(
        hashlib.sha256(observation.tobytes()).hexdigest()
        for observation in observations
    )
    rounded = Counter(
        hashlib.sha256(np.round(observation, 3).tobytes()).hexdigest()
        for observation in observations
    )
    episode_counts = Counter(row["episode_id"] for row in corrections)
    teacher_actions = Counter(int(row["action"]) for row in teacher)
    correction_actions = Counter(int(row["action"]) for row in corrections)
    learner_actions = Counter(int(row["learner_action"]) for row in corrections)
    action_pairs = Counter(
        f"{row['learner_action']}->{row['action']}" for row in corrections
    )
    category_action = Counter(
        f"{row['failure_category']}|{row['action']}" for row in corrections
    )

    cluster_rows = []
    for cluster in range(12):
        indices = np.flatnonzero(labels == cluster)
        cluster_categories = Counter(
            corrections[index]["failure_category"] for index in indices
        )
        cluster_actions = Counter(
            int(corrections[index]["action"]) for index in indices
        )
        cluster_episodes = Counter(
            corrections[index]["episode_id"] for index in indices
        )
        cluster_rows.append(
            {
                "cluster": cluster,
                "records": len(indices),
                "share": len(indices) / len(corrections),
                "dominant_category": cluster_categories.most_common(1)[0][0],
                "dominant_category_share": (
                    cluster_categories.most_common(1)[0][1] / len(indices)
                ),
                "release": cluster_actions[0],
                "left": cluster_actions[1],
                "right": cluster_actions[2],
                "episodes": len(cluster_episodes),
                "largest_episode_share": (
                    cluster_episodes.most_common(1)[0][1] / len(indices)
                ),
            }
        )

    output = {
        "correction_records": len(corrections),
        "base_train_records": len(teacher),
        "correction_to_base_ratio": len(corrections) / len(teacher),
        "exact_duplicate_records": sum(
            count - 1 for count in exact.values() if count > 1
        ),
        "exact_duplicate_ratio": sum(
            count - 1 for count in exact.values() if count > 1
        )
        / len(corrections),
        "rounded_3dp_duplicate_records": sum(
            count - 1 for count in rounded.values() if count > 1
        ),
        "rounded_3dp_duplicate_ratio": sum(
            count - 1 for count in rounded.values() if count > 1
        )
        / len(corrections),
        "episodes": len(episode_counts),
        "episode_record_min": min(episode_counts.values()),
        "episode_record_median": float(np.median(list(episode_counts.values()))),
        "episode_record_max": max(episode_counts.values()),
        "largest_episode_share": max(episode_counts.values()) / len(corrections),
        "base_train_action_counts": {
            str(action): teacher_actions[action] for action in range(3)
        },
        "correction_teacher_action_counts": {
            str(action): correction_actions[action] for action in range(3)
        },
        "correction_learner_action_counts": {
            str(action): learner_actions[action] for action in range(3)
        },
        "learner_to_teacher_action_pairs": dict(action_pairs),
        "category_by_teacher_action": dict(category_action),
        "clusters": cluster_rows,
    }
    Path("artifacts/dagger0_correction_audit.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with Path("artifacts/dagger0_correction_clusters.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=cluster_rows[0].keys())
        writer.writeheader()
        writer.writerows(cluster_rows)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
