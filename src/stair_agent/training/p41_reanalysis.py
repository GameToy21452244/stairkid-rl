"""Selection-only safeguards for the P4.1 checkpoint reanalysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .p41_ablation import selection_key
from .p41_sequence import P41_VARIANTS


P41_REANALYSIS_SCHEMA_VERSION = "p41-checkpoint-reanalysis-v1"


@dataclass(frozen=True)
class SelectionOnlySource:
    dataset_sha256: str
    selection_seeds: tuple[int, ...]
    final_seeds: tuple[int, ...]

    def __getitem__(self, key: str):
        return getattr(self, key)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} 必須是 object。")
    return value


def _integer_sequence(value: object, *, label: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} 必須是整數序列。")
    result = tuple(int(item) for item in value)
    if not result or len(result) != len(set(result)):
        raise ValueError(f"{label} 不可為空或重複。")
    return result


def validate_selection_only_source(summary: Mapping[str, object]) -> SelectionOnlySource:
    """Reject artifacts that are not the untouched P4.1 selection failure."""

    if summary.get("experiment") != "P4.1-bounded-S0-S1-S2-S3-ablation-v1":
        raise ValueError("不是既定 P4.1 bounded experiment。")
    if summary.get("status") != "FAIL_STOP_SELECTION":
        raise ValueError("重分析只接受 FAIL_STOP_SELECTION 來源。")
    if summary.get("selected_architecture") is not None:
        raise ValueError("來源已有 selected architecture，拒絕 selection-only 重分析。")
    if summary.get("final_gate_vs_s0") is not None or summary.get("final_summaries") not in ({}, None):
        raise ValueError("來源已使用 final evidence，拒絕重分析。")
    manifest = _mapping(summary.get("manifest"), label="manifest")
    dataset = _mapping(manifest.get("dataset"), label="manifest.dataset")
    dataset_sha256 = str(dataset.get("sha256", ""))
    if len(dataset_sha256) != 64:
        raise ValueError("dataset SHA-256 無效。")
    protocol = _mapping(manifest.get("protocol"), label="manifest.protocol")
    selection_seeds = _integer_sequence(
        protocol.get("selection_environment_seeds"),
        label="selection seeds",
    )
    final_seeds = _integer_sequence(
        protocol.get("final_environment_seeds"),
        label="final seeds",
    )
    if set(selection_seeds) & set(final_seeds):
        raise ValueError("selection/final seeds 重疊。")
    return SelectionOnlySource(dataset_sha256, selection_seeds, final_seeds)


def _candidate_rank(candidate: Mapping[str, object]) -> tuple:
    rollout = dict(_mapping(candidate.get("selection_rollout"), label="selection rollout"))
    # Historical artifacts do not have the corrected release-bridged metric.
    # The old direct-switch value is used only as the last risk-first tie-break;
    # replayed checkpoints receive the new telemetry before any new Gate decision.
    rollout.setdefault(
        "direction_reversals_per_100_steps",
        rollout.get("direction_switches_per_100_steps", float("inf")),
    )
    validation = _mapping(candidate.get("validation"), label="validation")
    return selection_key(
        rollout,
        float(validation.get("loss", float("inf"))),
        int(candidate.get("update", -1)),
    )


def risk_first_selected_updates(
    summary: Mapping[str, object],
) -> dict[str, dict[int, int]]:
    training = _mapping(summary.get("training"), label="training")
    selected: dict[str, dict[int, int]] = {}
    for variant in P41_VARIANTS:
        records = training.get(variant)
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise ValueError(f"training.{variant} 必須是序列。")
        by_seed: dict[int, int] = {}
        for record_value in records:
            record = _mapping(record_value, label=f"training.{variant} record")
            seed = int(record.get("initialization_seed", -1))
            candidates = record.get("candidates")
            if not isinstance(candidates, Sequence) or not candidates:
                raise ValueError(f"{variant} seed {seed} 缺少 candidates。")
            normalized = [
                _mapping(candidate, label=f"{variant} seed {seed} candidate")
                for candidate in candidates
            ]
            chosen = max(normalized, key=_candidate_rank)
            by_seed[seed] = int(chosen.get("update", -1))
        if sorted(by_seed) != [0, 1, 2] or any(update <= 0 for update in by_seed.values()):
            raise ValueError(f"{variant} initialization seeds 或 update 無效。")
        selected[variant] = by_seed
    return selected


__all__ = [
    "P41_REANALYSIS_SCHEMA_VERSION",
    "SelectionOnlySource",
    "risk_first_selected_updates",
    "validate_selection_only_source",
]
