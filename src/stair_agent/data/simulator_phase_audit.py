"""Decision-level observability audit for simulator Teacher phase aliases."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any, Iterable, Mapping


DEPLOYABLE_FIELDS = (
    "motion",
    "velocity_y",
    "nearest_gap",
    "support_heuristic",
    "landed_event",
    "floor_descended_event",
    "edge_distance",
    "visible_platform_count",
    "health_segments",
    "steps_since_landing_event",
)


def _bin_velocity_y(value: float) -> str:
    # GameObservation uses screen coordinates: negative y moves upward and
    # positive y moves downward.  Keep the coordinate system explicit in the
    # labels so diagnostic reports cannot invert physical motion semantics.
    if value < -40.0:
        return "strong_upward_screen"
    if value < 0.0:
        return "weak_upward_screen"
    if value <= 40.0:
        return "weak_downward_screen"
    return "strong_downward_screen"


def _bin_gap(value: float | None) -> str:
    if value is None:
        return "missing"
    if value <= 3.0:
        return "0_3"
    if value <= 6.0:
        return "3_6"
    if value <= 12.0:
        return "6_12"
    return "over_12"


def _bin_edge(value: float | None) -> str:
    if value is None:
        return "missing"
    if value <= 12.0:
        return "0_12"
    if value <= 24.0:
        return "12_24"
    return "over_24"


def _bin_landing_recency(value: int | None) -> str:
    if value is None:
        return "missing"
    if value == 0:
        return "0"
    if value <= 2:
        return "1_2"
    if value <= 4:
        return "3_4"
    return "5_plus"


def phase_signature(sample: Mapping[str, object]) -> str:
    return "|".join(
        (
            str(sample["motion"]),
            _bin_velocity_y(float(sample["velocity_y"])),
            _bin_gap(
                None
                if sample["nearest_gap"] is None
                else float(sample["nearest_gap"])
            ),
            str(bool(sample["support_heuristic"])),
            str(bool(sample["landed_event"])),
            str(bool(sample["floor_descended_event"])),
            _bin_landing_recency(
                None
                if sample["steps_since_landing_event"] is None
                else int(sample["steps_since_landing_event"])
            ),
            _bin_edge(
                None
                if sample["edge_distance"] is None
                else float(sample["edge_distance"])
            ),
            str(sample.get("nearest_platform_kind") or "none"),
        )
    )


def _fields_complete(samples: Iterable[Mapping[str, object]]) -> bool:
    for sample in samples:
        if any(field not in sample for field in DEPLOYABLE_FIELDS):
            return False
        for field in ("velocity_y", "nearest_gap", "edge_distance"):
            value = sample[field]
            if value is not None and not math.isfinite(float(value)):
                return False
    return True


def summarize_phase_observability(
    first_divergences: list[dict[str, object]],
    all_samples: list[dict[str, object]],
    *,
    expected_episodes: int = 60,
) -> dict[str, Any]:
    outcomes = Counter(
        str(sample.get("intervention_outcome", "unknown"))
        for sample in first_divergences
    )
    signature_outcomes: dict[str, set[str]] = defaultdict(set)
    signature_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for sample in first_divergences:
        signature = phase_signature(sample)
        outcome = str(sample.get("intervention_outcome", "unknown"))
        signature_outcomes[signature].add(outcome)
        signature_counts[signature][outcome] += 1
        sample["deployable_phase_signature"] = signature
    improved_regressed_conflicts = sorted(
        signature
        for signature, labels in signature_outcomes.items()
        if "improved" in labels and "regressed" in labels
    )
    improved_non_improved_conflicts = sorted(
        signature
        for signature, labels in signature_outcomes.items()
        if "improved" in labels and labels - {"improved"}
    )
    support_rows = [
        sample for sample in all_samples if bool(sample["support_heuristic"])
    ]
    support_by_motion = Counter(str(row["motion"]) for row in support_rows)
    support_by_outcome = Counter(
        str(row.get("base_outcome", "unknown")) for row in support_rows
    )
    support_by_reason = Counter(
        str(row.get("base_reason", "unknown")) for row in support_rows
    )
    checks = {
        "first_divergence_for_every_episode": (
            len(first_divergences) == expected_episodes
        ),
        "deployable_fields_complete": _fields_complete(first_divergences),
        "changed_outcome_episodes_at_least_20": (
            outcomes["improved"] + outcomes["regressed"] >= 20
        ),
        "improved_episodes_at_least_10": outcomes["improved"] >= 10,
        "regressed_episodes_at_least_10": outcomes["regressed"] >= 10,
        "no_improved_regressed_signature_conflict": (
            not improved_regressed_conflicts
        ),
    }
    evidence_sufficient = all(
        checks[name]
        for name in (
            "first_divergence_for_every_episode",
            "deployable_fields_complete",
            "changed_outcome_episodes_at_least_20",
            "improved_episodes_at_least_10",
            "regressed_episodes_at_least_10",
        )
    )
    passed = evidence_sufficient and checks[
        "no_improved_regressed_signature_conflict"
    ]
    return {
        "status": (
            "PASS_PHASE_OBSERVABILITY"
            if passed
            else (
                "FAIL_PHASE_SIGNATURE_ALIAS"
                if evidence_sufficient
                else "INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL"
            )
        ),
        "passed": passed,
        "evidence_sufficient": evidence_sufficient,
        "checks": checks,
        "criteria": {
            "expected_first_divergences": expected_episodes,
            "changed_outcome_episodes_minimum": 20,
            "improved_episodes_minimum": 10,
            "regressed_episodes_minimum": 10,
            "signature_conflict_policy": (
                "No identical deployable signature may contain both improved "
                "and regressed interventions."
            ),
        },
        "first_divergence_outcomes": dict(sorted(outcomes.items())),
        "unique_phase_signatures": len(signature_outcomes),
        "signature_counts": {
            signature: dict(sorted(counts.items()))
            for signature, counts in sorted(signature_counts.items())
        },
        "improved_regressed_signature_conflicts": (
            improved_regressed_conflicts
        ),
        "improved_non_improved_signature_conflicts": (
            improved_non_improved_conflicts
        ),
        "support_overlap": {
            "rows": len(support_rows),
            "episodes": len({int(row["seed"]) for row in support_rows}),
            "by_motion": dict(sorted(support_by_motion.items())),
            "by_base_outcome": dict(sorted(support_by_outcome.items())),
            "top_base_reasons": dict(support_by_reason.most_common(12)),
        },
    }


__all__ = [
    "DEPLOYABLE_FIELDS",
    "phase_signature",
    "summarize_phase_observability",
]
