"""Held-out separability Gate for deployable simulator Teacher context."""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Mapping, Sequence

import numpy as np


VARIANTS = (
    "phase_basic",
    "causal_action",
    "target_relative",
    "combined",
)
MOTION_KINDS = ("rising", "falling", "stable", "missing")
PLATFORM_KINDS = (
    "normal",
    "spikes",
    "spring",
    "conveyor",
    "flipping",
    "none",
)
REQUIRED_FIELDS = (
    "seed",
    "split",
    "intervention_outcome",
    "motion",
    "velocity_x",
    "velocity_y",
    "nearest_gap",
    "nearest_platform_kind",
    "support_heuristic",
    "landed_event",
    "floor_descended_event",
    "steps_since_landing_event",
    "edge_distance",
    "visible_platform_count",
    "health_segments",
    "shadow_action",
    "causal_action_state",
    "target_present",
    "target_matched",
    "target_signed_offset",
    "target_center_delta",
    "target_top_delta",
    "target_safe_left_delta",
    "target_safe_right_delta",
    "target_platform_kind",
)


def _one_hot(value: object, choices: Sequence[object]) -> list[float]:
    return [float(value == choice) for choice in choices]


def _number_and_missing(
    value: object,
    *,
    scale: float,
) -> list[float]:
    if value is None:
        return [0.0, 1.0]
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("Schema probe feature含非有限數值。")
    return [numeric / scale, 0.0]


def _basic_features(row: Mapping[str, object]) -> list[float]:
    motion = str(row.get("motion") or "missing")
    if motion not in MOTION_KINDS:
        motion = "missing"
    nearest_kind = str(row.get("nearest_platform_kind") or "none")
    if nearest_kind not in PLATFORM_KINDS:
        nearest_kind = "none"
    shadow_action = int(row["shadow_action"])
    if shadow_action not in {0, 1, 2}:
        raise ValueError("shadow action無效。")
    recency = row["steps_since_landing_event"]
    return [
        *_one_hot(motion, MOTION_KINDS),
        float(row["velocity_y"]) / 230.0,
        *_number_and_missing(row["nearest_gap"], scale=100.0),
        float(bool(row["support_heuristic"])),
        float(bool(row["landed_event"])),
        float(bool(row["floor_descended_event"])),
        *_number_and_missing(
            None if recency is None else min(int(recency), 8),
            scale=8.0,
        ),
        *_number_and_missing(row["edge_distance"], scale=200.0),
        *_one_hot(nearest_kind, PLATFORM_KINDS),
        min(int(row["visible_platform_count"]), 10) / 10.0,
        min(int(row["health_segments"]), 12) / 12.0,
        *_one_hot(shadow_action, (0, 1, 2)),
    ]


def _causal_features(row: Mapping[str, object]) -> list[float]:
    state = np.asarray(row["causal_action_state"], dtype=np.float64)
    if state.shape != (9,) or not np.isfinite(state).all():
        raise ValueError("causal action state必須是有限9維向量。")
    return [float(row["velocity_x"]) / 230.0, *state.tolist()]


def _target_features(row: Mapping[str, object]) -> list[float]:
    target_kind = str(row.get("target_platform_kind") or "none")
    if target_kind not in PLATFORM_KINDS:
        target_kind = "none"
    return [
        float(bool(row["target_present"])),
        float(bool(row["target_matched"])),
        *_number_and_missing(row["target_signed_offset"], scale=400.0),
        *_number_and_missing(row["target_center_delta"], scale=400.0),
        *_number_and_missing(row["target_top_delta"], scale=431.0),
        *_number_and_missing(row["target_safe_left_delta"], scale=400.0),
        *_number_and_missing(row["target_safe_right_delta"], scale=400.0),
        *_one_hot(target_kind, PLATFORM_KINDS),
    ]


def build_feature_vector(
    row: Mapping[str, object],
    variant: str,
) -> np.ndarray:
    if variant not in VARIANTS:
        raise ValueError(f"未知schema probe variant：{variant!r}")
    basic = _basic_features(row)
    values = list(basic)
    if variant in {"causal_action", "combined"}:
        values.extend(_causal_features(row))
    if variant in {"target_relative", "combined"}:
        values.extend(_target_features(row))
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or not np.isfinite(result).all():
        raise ValueError("Schema probe feature vector無效。")
    return result


def _fields_complete(rows: Sequence[Mapping[str, object]]) -> bool:
    for row in rows:
        if any(field not in row for field in REQUIRED_FIELDS):
            return False
        try:
            for variant in VARIANTS:
                build_feature_vector(row, variant)
        except (TypeError, ValueError, OverflowError):
            return False
    return True


def _contains_forbidden_identity(rows: Sequence[Mapping[str, object]]) -> bool:
    forbidden_exact = {
        "last_landed_floor",
        "deepest_floor",
        "physical_velocity_y",
        "privileged_phase",
    }
    for row in rows:
        for key in row:
            lowered = str(key).lower()
            if lowered in forbidden_exact or lowered.endswith("_id"):
                return True
    return False


def _label(row: Mapping[str, object]) -> int:
    outcome = str(row["intervention_outcome"])
    if outcome == "improved":
        return 1
    if outcome == "regressed":
        return 0
    raise ValueError(f"非changed outcome：{outcome!r}")


def _metric_unavailable(records: int) -> dict[str, object]:
    return {
        "available": False,
        "records": records,
        "accuracy": None,
        "balanced_accuracy": None,
        "opposite_nearest_neighbor_rate": None,
        "confusion_matrix": None,
    }


def _knn_metrics(
    development: Sequence[Mapping[str, object]],
    query: Sequence[Mapping[str, object]],
    *,
    variant: str,
    leave_one_seed_out: bool,
    neighbors: int = 5,
) -> dict[str, object]:
    if not development or not query:
        return _metric_unavailable(len(query))
    reference_x = np.stack(
        [build_feature_vector(row, variant) for row in development]
    )
    reference_y = np.asarray([_label(row) for row in development], dtype=np.int64)
    if len(set(reference_y.tolist())) != 2:
        return _metric_unavailable(len(query))
    mean = reference_x.mean(axis=0)
    scale = reference_x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    reference_x = (reference_x - mean) / scale
    reference_seeds = np.asarray([int(row["seed"]) for row in development])

    truths: list[int] = []
    predictions: list[int] = []
    nearest_opposite: list[bool] = []
    for row in query:
        vector = (build_feature_vector(row, variant) - mean) / scale
        distances = np.linalg.norm(reference_x - vector, axis=1)
        eligible = np.ones(len(development), dtype=bool)
        if leave_one_seed_out:
            eligible &= reference_seeds != int(row["seed"])
        indices = np.flatnonzero(eligible)
        if not len(indices):
            return _metric_unavailable(len(query))
        ordered = indices[np.argsort(distances[indices], kind="stable")]
        selected = ordered[: min(neighbors, len(ordered))]
        votes = reference_y[selected]
        prediction = int(votes.sum() * 2 > len(votes))
        truth = _label(row)
        truths.append(truth)
        predictions.append(prediction)
        nearest_opposite.append(bool(reference_y[ordered[0]] != truth))

    truth_array = np.asarray(truths, dtype=np.int64)
    prediction_array = np.asarray(predictions, dtype=np.int64)
    if len(set(truths)) != 2:
        return _metric_unavailable(len(query))
    confusion = np.zeros((2, 2), dtype=np.int64)
    for truth, prediction in zip(truths, predictions, strict=True):
        confusion[truth, prediction] += 1
    recalls = [
        confusion[label, label] / max(1, confusion[label].sum())
        for label in (0, 1)
    ]
    return {
        "available": True,
        "records": len(query),
        "accuracy": float(np.mean(truth_array == prediction_array)),
        "balanced_accuracy": float(np.mean(recalls)),
        "opposite_nearest_neighbor_rate": float(np.mean(nearest_opposite)),
        "confusion_matrix": confusion.tolist(),
        "label_order": ["regressed", "improved"],
    }


def _at_least(value: object, threshold: float) -> bool:
    return value is not None and float(value) >= threshold


def _improves_by(candidate: object, base: object, threshold: float) -> bool:
    return (
        candidate is not None
        and base is not None
        and float(candidate) - float(base) >= threshold
    )


def _decreases_by(candidate: object, base: object, threshold: float) -> bool:
    return (
        candidate is not None
        and base is not None
        and float(base) - float(candidate) >= threshold
    )


def summarize_observation_schema_probe(
    rows: list[dict[str, object]],
    *,
    expected_episodes: int = 400,
) -> dict[str, Any]:
    outcomes = Counter(str(row["intervention_outcome"]) for row in rows)
    by_split: dict[str, Counter[str]] = {
        split: Counter(
            str(row["intervention_outcome"])
            for row in rows
            if str(row["split"]) == split
        )
        for split in ("development", "validation", "test")
    }
    changed = [
        row
        for row in rows
        if str(row["intervention_outcome"]) in {"improved", "regressed"}
    ]
    development = [row for row in changed if row["split"] == "development"]
    metrics: dict[str, dict[str, dict[str, object]]] = {}
    for variant in VARIANTS:
        metrics[variant] = {}
        for split in ("development", "validation", "test"):
            query = [row for row in changed if row["split"] == split]
            metrics[variant][split] = _knn_metrics(
                development,
                query,
                variant=variant,
                leave_one_seed_out=split == "development",
            )

    validation_basic = metrics["phase_basic"]["validation"]
    validation_combined = metrics["combined"]["validation"]
    test_basic = metrics["phase_basic"]["test"]
    test_combined = metrics["combined"]["test"]
    forbidden = _contains_forbidden_identity(rows)
    checks = {
        "first_divergence_for_all_400_episodes": len(rows) == expected_episodes,
        "deployable_fields_complete_and_finite": _fields_complete(rows),
        "no_raw_identity_or_privileged_feature": not forbidden,
        "changed_outcomes_at_least_40": len(changed) >= 40,
        "improved_outcomes_at_least_10": outcomes["improved"] >= 10,
        "regressed_outcomes_at_least_10": outcomes["regressed"] >= 10,
        "validation_changed_at_least_8": (
            by_split["validation"]["improved"]
            + by_split["validation"]["regressed"]
            >= 8
        ),
        "validation_each_class_at_least_2": min(
            by_split["validation"]["improved"],
            by_split["validation"]["regressed"],
        )
        >= 2,
        "test_changed_at_least_8": (
            by_split["test"]["improved"]
            + by_split["test"]["regressed"]
            >= 8
        ),
        "test_each_class_at_least_2": min(
            by_split["test"]["improved"],
            by_split["test"]["regressed"],
        )
        >= 2,
        "combined_validation_balanced_accuracy_at_least_0_65": _at_least(
            validation_combined["balanced_accuracy"], 0.65
        ),
        "combined_test_balanced_accuracy_at_least_0_65": _at_least(
            test_combined["balanced_accuracy"], 0.65
        ),
        "combined_validation_improves_basic_by_0_10": _improves_by(
            validation_combined["balanced_accuracy"],
            validation_basic["balanced_accuracy"],
            0.10,
        ),
        "combined_test_improves_basic_by_0_10": _improves_by(
            test_combined["balanced_accuracy"],
            test_basic["balanced_accuracy"],
            0.10,
        ),
        "combined_test_opposite_neighbor_rate_drops_by_0_10": _decreases_by(
            test_combined["opposite_nearest_neighbor_rate"],
            test_basic["opposite_nearest_neighbor_rate"],
            0.10,
        ),
    }
    evidence_checks = (
        "first_divergence_for_all_400_episodes",
        "deployable_fields_complete_and_finite",
        "no_raw_identity_or_privileged_feature",
        "changed_outcomes_at_least_40",
        "improved_outcomes_at_least_10",
        "regressed_outcomes_at_least_10",
        "validation_changed_at_least_8",
        "validation_each_class_at_least_2",
        "test_changed_at_least_8",
        "test_each_class_at_least_2",
    )
    evidence_sufficient = all(checks[name] for name in evidence_checks)
    passed = evidence_sufficient and all(checks.values())
    return {
        "status": (
            "PASS_OBSERVATION_SCHEMA_PROBE"
            if passed
            else (
                "FAIL_STOP_SCHEMA_NOT_SEPARABLE"
                if evidence_sufficient
                else "INSUFFICIENT_EVIDENCE_STOP_SCHEMA_PROBE"
            )
        ),
        "passed": passed,
        "evidence_sufficient": evidence_sufficient,
        "checks": checks,
        "criteria": {
            "episodes": expected_episodes,
            "changed_minimum": 40,
            "improved_minimum": 10,
            "regressed_minimum": 10,
            "validation_test_changed_minimum": 8,
            "validation_test_each_class_minimum": 2,
            "balanced_accuracy_minimum": 0.65,
            "balanced_accuracy_improvement_minimum": 0.10,
            "opposite_neighbor_rate_reduction_minimum": 0.10,
            "neighbors": 5,
        },
        "outcomes": dict(sorted(outcomes.items())),
        "outcomes_by_split": {
            split: dict(sorted(counts.items()))
            for split, counts in by_split.items()
        },
        "metrics": metrics,
        "feature_dimensions": {
            variant: int(build_feature_vector(rows[0], variant).shape[0])
            if rows
            else None
            for variant in VARIANTS
        },
    }


__all__ = [
    "REQUIRED_FIELDS",
    "VARIANTS",
    "build_feature_vector",
    "summarize_observation_schema_probe",
]
