"""Offline state-aliasing audit for real-game Teacher trajectories.

The real-game controller sidecar is written after ``policy.choose``.  Its
same-step snapshot therefore contains post-decision state and must not be fed
to a Student that predicts that same action.  This module keeps that snapshot
for a leakage-ceiling diagnostic, while the deployable comparison shifts it
by one step within each episode.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import json
import math

import numpy as np


ACTION_NAMES = {0: "RELEASE_ALL", 1: "LEFT", 2: "RIGHT"}
ACTION_VALUES = {name: value for value, name in ACTION_NAMES.items()}

AUDIT_K = 5
MIN_REAL_ROWS = 500
MIN_RELATIVE_DISAGREEMENT_REDUCTION = 0.10
MIN_ENTROPY_REDUCTION_BITS = 0.05
MIN_ACCURACY_GAIN = 0.03
BOOTSTRAP_SAMPLES = 2_000
BOOTSTRAP_SEED = 20260803

PHASE_BRANCHES = ("launch", "move", "brake", "recovery")
KIND_BRANCHES = ("spike", "conveyor", "spring", "flip")


@dataclass(frozen=True)
class AuditRow:
    episode: str
    source: str
    step: int
    observation: np.ndarray
    action: int
    action_name: str
    teacher_reason: str
    controller_phase: str
    target_kind: str | None
    special_kind: str | None
    target_direction: str
    control_loop_hz: float | None
    post_memory: dict[str, object]
    causal_memory: dict[str, object]


@dataclass(frozen=True)
class KnnResult:
    indices: np.ndarray
    distances: np.ndarray
    pairwise_distances: np.ndarray
    active_dimensions: int
    zero_variance_dimensions: int


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(payload)
    return rows


def _target_direction(offset: object) -> str:
    if not isinstance(offset, (int, float)) or not math.isfinite(float(offset)):
        return "unknown"
    value = float(offset)
    if value < -5.0:
        return "left"
    if value > 5.0:
        return "right"
    return "aligned"


def align_episode_rows(
    transitions: Sequence[Mapping[str, object]],
    controllers: Sequence[Mapping[str, object]],
    *,
    episode: str,
    source: str,
) -> list[AuditRow]:
    """Align transition and sidecar rows and create causal memory snapshots."""

    if len(transitions) != len(controllers):
        raise ValueError(
            f"{source}: transition/controller count mismatch "
            f"({len(transitions)} != {len(controllers)})"
        )
    aligned: list[AuditRow] = []
    previous_post_memory: dict[str, object] = {}
    for index, (transition, controller) in enumerate(zip(transitions, controllers)):
        transition_step = int(transition.get("step", -1))
        controller_step = int(controller.get("step", -2))
        if transition_step != controller_step:
            raise ValueError(
                f"{source}: step mismatch at row {index}: "
                f"{transition_step} != {controller_step}"
            )
        action = int(transition.get("action", -1))
        if action not in ACTION_NAMES:
            raise ValueError(f"{source}: unsupported action {action} at step {transition_step}")
        action_name = str(controller.get("action", ""))
        if ACTION_NAMES[action] != action_name:
            raise ValueError(
                f"{source}: action mismatch at step {transition_step}: "
                f"{ACTION_NAMES[action]} != {action_name}"
            )
        observation = np.asarray(transition.get("observation"), dtype=np.float64)
        if observation.shape != (268,):
            raise ValueError(
                f"{source}: observation at step {transition_step} has shape "
                f"{observation.shape}, expected (268,)"
            )
        if not np.isfinite(observation).all():
            raise ValueError(f"{source}: non-finite observation at step {transition_step}")
        memory_value = controller.get("controller_memory")
        post_memory = dict(memory_value) if isinstance(memory_value, Mapping) else {}
        loop_hz_value = controller.get("control_loop_hz")
        loop_hz = (
            float(loop_hz_value)
            if isinstance(loop_hz_value, (int, float))
            and math.isfinite(float(loop_hz_value))
            and float(loop_hz_value) > 0
            else None
        )
        target_kind_value = transition.get("target_platform_kind")
        special_kind_value = post_memory.get("special_source_platform_kind")
        aligned.append(
            AuditRow(
                episode=episode,
                source=source,
                step=transition_step,
                observation=observation,
                action=action,
                action_name=action_name,
                teacher_reason=str(controller.get("teacher_reason", "unknown")),
                controller_phase=str(post_memory.get("controller_phase", "unknown")),
                target_kind=(
                    None if target_kind_value in {None, ""} else str(target_kind_value)
                ),
                special_kind=(
                    None if special_kind_value in {None, ""} else str(special_kind_value)
                ),
                target_direction=_target_direction(transition.get("target_signed_offset")),
                control_loop_hz=loop_hz,
                post_memory=post_memory,
                causal_memory=dict(previous_post_memory),
            )
        )
        previous_post_memory = post_memory
    return aligned


def load_real_gate_rows(gate_artifact: Path) -> tuple[list[AuditRow], dict[str, object]]:
    gate_payload = json.loads(gate_artifact.read_text(encoding="utf-8"))
    gate = gate_payload.get("gate", {})
    if gate.get("status") != "PASS" or gate.get("passed") is not True:
        raise ValueError(f"source Gate is not PASS: {gate_artifact}")
    audit = gate_payload.get("audit", {})
    sidecars = audit.get("sidecars", [])
    if not isinstance(sidecars, list) or not sidecars:
        raise ValueError(f"source Gate has no sidecar manifest: {gate_artifact}")

    rows: list[AuditRow] = []
    sources: list[dict[str, object]] = []
    for item in sidecars:
        sidecar_path = Path(str(item["path"]))
        if not sidecar_path.exists():
            raise FileNotFoundError(sidecar_path)
        transition_path = sidecar_path.with_name(
            sidecar_path.name.replace(".controller.jsonl", ".transitions.jsonl")
        )
        if not transition_path.exists():
            raise FileNotFoundError(transition_path)
        episode_number = int(item["episode"])
        episode = f"episode_{episode_number:02d}"
        source = f"{sidecar_path.parent.name}/{episode}"
        episode_rows = align_episode_rows(
            _read_jsonl(transition_path),
            _read_jsonl(sidecar_path),
            episode=episode,
            source=source,
        )
        expected_records = int(item.get("records", len(episode_rows)))
        if len(episode_rows) != expected_records:
            raise ValueError(
                f"{source}: manifest count {expected_records} != {len(episode_rows)}"
            )
        rows.extend(episode_rows)
        sources.append(
            {
                "episode": episode,
                "sidecar": str(sidecar_path),
                "transitions": str(transition_path),
                "records": len(episode_rows),
            }
        )
    metadata: dict[str, object] = {
        "gate_artifact": str(gate_artifact.resolve()),
        "source_experiment": gate_payload.get("experiment"),
        "source_gate_status": gate.get("status"),
        "episodes": len(sidecars),
        "rows": len(rows),
        "sources": sources,
    }
    return rows, metadata


def _is_unstable_identifier(key: str) -> bool:
    return key.endswith("_id") or key.endswith("_ids") or "episode_id" in key


def _selected_memory_keys(
    memories: Sequence[Mapping[str, object]], allowed_keys: set[str] | None
) -> tuple[list[str], list[str]]:
    all_keys = sorted({str(key) for memory in memories for key in memory})
    excluded = [key for key in all_keys if _is_unstable_identifier(key)]
    selected = [key for key in all_keys if key not in excluded]
    if allowed_keys is not None:
        selected = [key for key in selected if key in allowed_keys]
    return selected, excluded


def build_memory_matrix(
    memories: Sequence[Mapping[str, object]],
    *,
    allowed_keys: set[str] | None = None,
    schema_memories: Sequence[Mapping[str, object]] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Encode controller memory without raw tracker IDs.

    ``schema_memories`` lets causal and post-decision matrices share the exact
    same columns, even though the first causal row of every episode is empty.
    """

    schema_source = list(schema_memories) if schema_memories is not None else list(memories)
    keys, excluded = _selected_memory_keys(schema_source, allowed_keys)
    columns: list[str] = []
    encoders: list[tuple[str, str, object | None]] = []
    for key in keys:
        values = [memory.get(key) for memory in schema_source]
        non_null = [value for value in values if value is not None]
        numeric = all(isinstance(value, (bool, int, float)) for value in non_null)
        if numeric:
            columns.append(key)
            encoders.append((key, "numeric", None))
            if any(value is None for value in values):
                columns.append(f"{key}__present")
                encoders.append((key, "present", None))
            continue
        categories = sorted({str(value) for value in non_null})
        categories.append("<NONE>")
        for category in categories:
            columns.append(f"{key}={category}")
            encoders.append((key, "category", category))

    matrix = np.zeros((len(memories), len(columns)), dtype=np.float64)
    for row_index, memory in enumerate(memories):
        for column_index, (key, mode, category) in enumerate(encoders):
            value = memory.get(key)
            if mode == "numeric":
                if isinstance(value, (bool, int, float)) and math.isfinite(float(value)):
                    matrix[row_index, column_index] = float(value)
            elif mode == "present":
                matrix[row_index, column_index] = float(value is not None)
            else:
                encoded = "<NONE>" if value is None else str(value)
                matrix[row_index, column_index] = float(encoded == category)
    return matrix, columns, excluded


def _standardized_pairwise(features: np.ndarray) -> tuple[np.ndarray, int, int]:
    if features.ndim != 2:
        raise ValueError("features must be a two-dimensional matrix")
    if not np.isfinite(features).all():
        raise ValueError("features contain NaN or infinity")
    standard_deviation = features.std(axis=0)
    active = standard_deviation > 1e-12
    active_count = int(active.sum())
    zero_count = int(features.shape[1] - active_count)
    if active_count == 0:
        return np.zeros((len(features), len(features))), 0, zero_count
    standardized = (features[:, active] - features[:, active].mean(axis=0)) / (
        standard_deviation[active]
    )
    squared_norm = np.sum(standardized * standardized, axis=1)
    distances = (
        squared_norm[:, None]
        + squared_norm[None, :]
        - 2.0 * standardized @ standardized.T
    ) / active_count
    np.maximum(distances, 0.0, out=distances)
    return distances, active_count, zero_count


def _neighbors_from_pairwise(
    pairwise: np.ndarray, episodes: np.ndarray, *, k: int
) -> tuple[np.ndarray, np.ndarray]:
    if len(pairwise) != len(episodes):
        raise ValueError("pairwise matrix and episode labels do not align")
    masked = pairwise.copy()
    same_episode = episodes[:, None] == episodes[None, :]
    masked[same_episode] = np.inf
    available = np.sum(np.isfinite(masked), axis=1)
    if np.any(available < k):
        raise ValueError("at least one row has fewer than k cross-episode neighbors")
    partition = np.argpartition(masked, kth=k - 1, axis=1)[:, :k]
    partition_distances = np.take_along_axis(masked, partition, axis=1)
    order = np.argsort(partition_distances, axis=1, kind="stable")
    indices = np.take_along_axis(partition, order, axis=1)
    distances = np.take_along_axis(masked, indices, axis=1)
    return indices, distances


def cross_episode_knn(
    features: np.ndarray, episodes: np.ndarray, *, k: int = AUDIT_K
) -> KnnResult:
    pairwise, active, zero = _standardized_pairwise(np.asarray(features, dtype=np.float64))
    indices, distances = _neighbors_from_pairwise(pairwise, episodes, k=k)
    return KnnResult(indices, distances, pairwise, active, zero)


def _combined_knn(
    observation_knn: KnnResult,
    memory_features: np.ndarray,
    episodes: np.ndarray,
    *,
    k: int,
) -> KnnResult:
    memory_pairwise, active, zero = _standardized_pairwise(memory_features)
    if active == 0:
        pairwise = observation_knn.pairwise_distances.copy()
    else:
        # Predeclared equal block weight prevents 268 observation dimensions
        # from automatically drowning out the smaller memory block.
        pairwise = 0.5 * observation_knn.pairwise_distances + 0.5 * memory_pairwise
    indices, distances = _neighbors_from_pairwise(pairwise, episodes, k=k)
    return KnnResult(indices, distances, pairwise, active, zero)


def _entropy(values: np.ndarray) -> float:
    counts = np.bincount(values.astype(np.int64), minlength=len(ACTION_NAMES))
    probabilities = counts[counts > 0] / counts.sum()
    return float(-np.sum(probabilities * np.log2(probabilities)))


def action_neighbor_metrics(knn: KnnResult, actions: np.ndarray) -> dict[str, object]:
    neighbor_actions = actions[knn.indices]
    disagreements = np.mean(neighbor_actions != actions[:, None], axis=1)
    entropies = np.asarray([_entropy(values) for values in neighbor_actions])
    predictions = np.asarray(
        [
            int(np.argmax(np.bincount(values, minlength=len(ACTION_NAMES))))
            for values in neighbor_actions
        ]
    )
    return {
        "neighbor_disagreement": float(disagreements.mean()),
        "conditional_entropy_bits": float(entropies.mean()),
        "knn_action_accuracy": float(np.mean(predictions == actions)),
        "mean_neighbor_distance": float(knn.distances.mean()),
        "row_disagreement": disagreements,
        "row_entropy": entropies,
        "row_correct": predictions == actions,
    }


def categorical_neighbor_metrics(knn: KnnResult, labels: Sequence[str]) -> dict[str, float]:
    labels_array = np.asarray(labels, dtype=object)
    categories = {value: index for index, value in enumerate(sorted(set(labels)))}
    encoded = np.asarray([categories[value] for value in labels], dtype=np.int64)
    neighbor_labels = encoded[knn.indices]
    entropies: list[float] = []
    correct: list[bool] = []
    agreements: list[float] = []
    for index, values in enumerate(neighbor_labels):
        counts = np.bincount(values, minlength=len(categories))
        probabilities = counts[counts > 0] / counts.sum()
        entropies.append(float(-np.sum(probabilities * np.log2(probabilities))))
        correct.append(int(np.argmax(counts)) == encoded[index])
        agreements.append(float(np.mean(values == encoded[index])))
    return {
        "knn_accuracy": float(np.mean(correct)),
        "neighbor_agreement": float(np.mean(agreements)),
        "conditional_entropy_bits": float(np.mean(entropies)),
    }


def _bootstrap_episode_improvement(
    rows: Sequence[AuditRow], base: np.ndarray, causal: np.ndarray
) -> dict[str, object]:
    episode_names = sorted({row.episode for row in rows})
    episode_improvements = []
    for episode in episode_names:
        mask = np.asarray([row.episode == episode for row in rows])
        episode_improvements.append(float(np.mean(base[mask] - causal[mask])))
    values = np.asarray(episode_improvements)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.choice(values, size=(BOOTSTRAP_SAMPLES, len(values)), replace=True)
    means = draws.mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return {
        "method": "paired episode-level bootstrap",
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "episode_mean_improvements": dict(zip(episode_names, episode_improvements)),
        "mean": float(values.mean()),
        "ci95_low": float(low),
        "ci95_high": float(high),
    }


def _duplicate_conflicts(
    observations: np.ndarray, actions: np.ndarray, episodes: np.ndarray, *, decimals: int | None
) -> dict[str, int]:
    values = observations if decimals is None else np.round(observations, decimals=decimals)
    groups: dict[bytes, list[int]] = {}
    for index, row in enumerate(values):
        groups.setdefault(np.ascontiguousarray(row).tobytes(), []).append(index)
    duplicated = [indices for indices in groups.values() if len(indices) > 1]
    conflicting = [
        indices
        for indices in duplicated
        if len(set(actions[indices].tolist())) > 1
        and len(set(episodes[indices].tolist())) > 1
    ]
    return {
        "duplicate_groups": len(duplicated),
        "duplicate_rows": sum(len(indices) for indices in duplicated),
        "cross_episode_action_conflict_groups": len(conflicting),
        "cross_episode_action_conflict_rows": sum(len(indices) for indices in conflicting),
    }


def _memory_group_keys(all_keys: Iterable[str]) -> dict[str, set[str]]:
    keys = {key for key in all_keys if not _is_unstable_identifier(key)}
    action = {
        key
        for key in keys
        if key
        in {
            "previous_action",
            "action_streak_steps",
            "active_direction",
            "pending_direction",
            "pending_frames",
            "release_frames",
            "post_launch_coast_frames",
        }
    }
    target = {
        key
        for key in keys
        if any(token in key for token in ("target", "landing_", "destination_"))
    }
    phase = {
        key
        for key in keys
        if key == "controller_phase"
        or key.endswith("_active")
        or "recovery" in key
        or "launch" in key
        or "escape" in key
        or "wall_" in key
    }
    support = {
        key
        for key in keys
        if "support" in key or "aligned" in key or "top_pressure" in key
    }
    return {
        "causal_action_history": action,
        "causal_target_context": target,
        "causal_phase_and_recovery": phase,
        "causal_support_context": support,
        "causal_full_memory": keys,
    }


def _branch_names(row: AuditRow) -> set[str]:
    branches: set[str] = set()
    if row.controller_phase in PHASE_BRANCHES:
        branches.add(row.controller_phase)
    if row.controller_phase in {"support_departure", "special_escape", "wall_guard", "aligned"}:
        branches.add(row.controller_phase)
    kinds = {row.target_kind, row.special_kind}
    if "spikes" in kinds:
        branches.add("spike")
    if "spring" in kinds:
        branches.add("spring")
    if "conveyor" in kinds:
        branches.add("conveyor")
    if "flipping" in kinds:
        branches.add("flip")
    return branches


def _public_metrics(metrics: Mapping[str, object]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in metrics.items()
        if not key.startswith("row_")
    }


def audit_state_aliasing(rows: Sequence[AuditRow], *, k: int = AUDIT_K) -> dict[str, object]:
    if not rows:
        raise ValueError("no rows supplied")
    observations = np.vstack([row.observation for row in rows])
    actions = np.asarray([row.action for row in rows], dtype=np.int64)
    episodes = np.asarray([row.episode for row in rows], dtype=object)
    post_memories = [row.post_memory for row in rows]
    causal_memories = [row.causal_memory for row in rows]

    observation_knn = cross_episode_knn(observations, episodes, k=k)
    representation_knn: dict[str, KnnResult] = {"observation_only": observation_knn}
    memory_columns: dict[str, list[str]] = {}
    all_memory_keys = {str(key) for memory in post_memories for key in memory}
    groups = _memory_group_keys(all_memory_keys)
    excluded_identifiers: set[str] = set()
    for name, keys in groups.items():
        matrix, columns, excluded = build_memory_matrix(
            causal_memories,
            allowed_keys=keys,
            schema_memories=post_memories,
        )
        memory_columns[name] = columns
        excluded_identifiers.update(excluded)
        representation_knn[name] = _combined_knn(
            observation_knn, matrix, episodes, k=k
        )
    post_matrix, post_columns, post_excluded = build_memory_matrix(post_memories)
    excluded_identifiers.update(post_excluded)
    memory_columns["post_decision_leakage_ceiling"] = post_columns
    representation_knn["post_decision_leakage_ceiling"] = _combined_knn(
        observation_knn, post_matrix, episodes, k=k
    )

    raw_metrics = {
        name: action_neighbor_metrics(knn, actions)
        for name, knn in representation_knn.items()
    }
    base = raw_metrics["observation_only"]
    causal = raw_metrics["causal_full_memory"]
    base_disagreement = float(base["neighbor_disagreement"])
    causal_disagreement = float(causal["neighbor_disagreement"])
    relative_reduction = (
        (base_disagreement - causal_disagreement) / base_disagreement
        if base_disagreement > 0
        else 0.0
    )
    entropy_reduction = float(base["conditional_entropy_bits"]) - float(
        causal["conditional_entropy_bits"]
    )
    accuracy_gain = float(causal["knn_action_accuracy"]) - float(
        base["knn_action_accuracy"]
    )
    bootstrap = _bootstrap_episode_improvement(
        rows,
        np.asarray(base["row_disagreement"]),
        np.asarray(causal["row_disagreement"]),
    )

    integrity_checks = {
        "source_gate_passed": True,
        "ten_episodes": len(set(episodes.tolist())) == 10,
        "minimum_500_rows": len(rows) >= MIN_REAL_ROWS,
        "observation_dim_268": observations.shape[1] == 268,
        "finite_observations": bool(np.isfinite(observations).all()),
        "cross_episode_neighbors_only": all(
            bool(np.all(episodes[index] != episodes[neighbors]))
            for index, neighbors in enumerate(observation_knn.indices)
        ),
        "raw_track_ids_excluded": not any(
            _is_unstable_identifier(column) for column in post_columns
        ),
        "post_decision_memory_excluded_from_gate": True,
    }
    gate_checks = {
        **integrity_checks,
        "relative_disagreement_reduction_at_least_10pct": (
            relative_reduction >= MIN_RELATIVE_DISAGREEMENT_REDUCTION
        ),
        "episode_bootstrap_ci_lower_nonnegative": float(bootstrap["ci95_low"]) >= 0.0,
        "entropy_or_accuracy_supporting_improvement": (
            entropy_reduction >= MIN_ENTROPY_REDUCTION_BITS
            or accuracy_gain >= MIN_ACCURACY_GAIN
        ),
    }
    gate_passed = all(gate_checks.values())

    branch_names = sorted({branch for row in rows for branch in _branch_names(row)})
    branch_metrics: dict[str, object] = {}
    for branch in branch_names:
        mask = np.asarray([branch in _branch_names(row) for row in rows])
        branch_metrics[branch] = {
            "rows": int(mask.sum()),
            "coverage_sufficient_for_directional_read": int(mask.sum()) >= 10,
            "observation_only": {
                key: float(np.mean(np.asarray(base[key])[mask]))
                for key in ("row_disagreement", "row_entropy", "row_correct")
            },
            "causal_full_memory": {
                key: float(np.mean(np.asarray(causal[key])[mask]))
                for key in ("row_disagreement", "row_entropy", "row_correct")
            },
        }

    active_observation = observations.std(axis=0) > 1e-12
    column_groups: dict[bytes, list[int]] = {}
    for column in np.flatnonzero(active_observation):
        payload = np.ascontiguousarray(observations[:, column]).tobytes()
        column_groups.setdefault(payload, []).append(int(column))
    duplicate_columns = [values for values in column_groups.values() if len(values) > 1]
    loop_rates = np.asarray(
        [row.control_loop_hz for row in rows if row.control_loop_hz is not None]
    )
    median_loop_hz = float(np.median(loop_rates)) if len(loop_rates) else None

    phase_labels = [row.controller_phase for row in rows]
    target_labels = [row.target_kind or "<NONE>" for row in rows]
    direction_labels = [row.target_direction for row in rows]
    predictability = {
        "phase_from_observation": categorical_neighbor_metrics(observation_knn, phase_labels),
        "phase_from_observation_plus_causal_memory": categorical_neighbor_metrics(
            representation_knn["causal_full_memory"], phase_labels
        ),
        "target_kind_from_observation": categorical_neighbor_metrics(
            observation_knn, target_labels
        ),
        "target_kind_from_observation_plus_causal_memory": categorical_neighbor_metrics(
            representation_knn["causal_full_memory"], target_labels
        ),
        "target_direction_from_observation": categorical_neighbor_metrics(
            observation_knn, direction_labels
        ),
        "target_direction_from_observation_plus_causal_memory": categorical_neighbor_metrics(
            representation_knn["causal_full_memory"], direction_labels
        ),
    }

    conflicts: list[dict[str, object]] = []
    causal_knn = representation_knn["causal_full_memory"]
    post_knn = representation_knn["post_decision_leakage_ceiling"]
    for index, row in enumerate(rows):
        if float(np.asarray(base["row_disagreement"])[index]) <= 0:
            continue
        valid = (episodes != row.episode) & (actions != row.action)
        candidate_indices = np.flatnonzero(valid)
        neighbor = int(
            candidate_indices[
                np.argmin(observation_knn.pairwise_distances[index, candidate_indices])
            ]
        )
        other = rows[neighbor]
        conflicts.append(
            {
                "query_source": row.source,
                "query_step": row.step,
                "query_action": row.action_name,
                "query_phase": row.controller_phase,
                "query_reason": row.teacher_reason,
                "query_target_kind": row.target_kind,
                "neighbor_source": other.source,
                "neighbor_step": other.step,
                "neighbor_action": other.action_name,
                "neighbor_phase": other.controller_phase,
                "neighbor_reason": other.teacher_reason,
                "neighbor_target_kind": other.target_kind,
                "observation_distance": float(
                    observation_knn.pairwise_distances[index, neighbor]
                ),
                "causal_memory_distance": float(causal_knn.pairwise_distances[index, neighbor]),
                "post_decision_leakage_distance": float(
                    post_knn.pairwise_distances[index, neighbor]
                ),
                "observation_knn_disagreement": float(
                    np.asarray(base["row_disagreement"])[index]
                ),
                "causal_knn_disagreement": float(
                    np.asarray(causal["row_disagreement"])[index]
                ),
            }
        )

    return {
        "protocol": {
            "k": k,
            "neighbor_scope": "cross-episode only",
            "distance": "z-score mean squared distance; observation and memory blocks weighted 0.5/0.5",
            "causal_memory_timing": "post-decision sidecar at t-1 shifted to decision t",
            "post_decision_timing": "same-step leakage ceiling only; excluded from Gate",
            "thresholds": {
                "minimum_rows": MIN_REAL_ROWS,
                "relative_disagreement_reduction": MIN_RELATIVE_DISAGREEMENT_REDUCTION,
                "entropy_reduction_bits": MIN_ENTROPY_REDUCTION_BITS,
                "accuracy_gain": MIN_ACCURACY_GAIN,
                "bootstrap_ci95_low": 0.0,
            },
        },
        "dataset": {
            "episodes": len(set(episodes.tolist())),
            "rows": len(rows),
            "observation_dimensions": observations.shape[1],
            "action_counts": {
                ACTION_NAMES[action]: int(np.sum(actions == action)) for action in ACTION_NAMES
            },
        },
        "exact_conflicts": _duplicate_conflicts(
            observations, actions, episodes, decimals=None
        ),
        "rounded_3_decimal_conflicts": _duplicate_conflicts(
            observations, actions, episodes, decimals=3
        ),
        "representations": {
            name: {
                **_public_metrics(metrics),
                "memory_dimensions": len(memory_columns.get(name, [])),
                "active_distance_block_dimensions": representation_knn[name].active_dimensions,
                "zero_variance_distance_block_dimensions": representation_knn[name].zero_variance_dimensions,
            }
            for name, metrics in raw_metrics.items()
        },
        "causal_memory_effect": {
            "absolute_disagreement_reduction": base_disagreement - causal_disagreement,
            "relative_disagreement_reduction": relative_reduction,
            "entropy_reduction_bits": entropy_reduction,
            "accuracy_gain": accuracy_gain,
            "bootstrap": bootstrap,
        },
        "predictability": predictability,
        "branches": branch_metrics,
        "feature_audit": {
            "observation_zero_variance_dimensions": int((~active_observation).sum()),
            "observation_active_dimensions": int(active_observation.sum()),
            "duplicate_active_column_groups": duplicate_columns,
            "raw_identifier_fields_excluded": sorted(excluded_identifiers),
            "causal_memory_columns": memory_columns["causal_full_memory"],
            "post_decision_leakage_fields": ["controller_phase", "previous_action", "action_streak_steps"],
            "time_since_landing_available": False,
            "time_since_landing_proxy": "lagged support_contact/aligned_dwell fields only",
            "observation_action_history_frames": 4,
            "median_control_loop_hz": median_loop_hz,
            "observation_action_history_seconds": (
                4.0 / median_loop_hz if median_loop_hz else None
            ),
        },
        "gate": {
            "status": "PASS" if gate_passed else "FAIL_STOP",
            "passed": gate_passed,
            "checks": gate_checks,
            "next_stage": (
                "P4.1_S0_S1_S2_S3_ABLATION"
                if gate_passed
                else "STOP_FIX_OBSERVATION_LABEL_TIMING_OR_COLLECT_MINIMAL_EVIDENCE"
            ),
        },
        "conflicts": conflicts,
    }
