"""Bounded training helpers for the P4.1 S0/S1/S2/S3 comparison."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .behavior_cloning import BehaviorCloningMLP
from .p41_sequence import (
    CAUSAL_ACTION_DIM,
    GRU_HIDDEN_SIZE,
    MLP_BATCH_SIZE,
    P41Dataset,
    P41_SCHEMA_VERSION,
    S1_INPUT_DIM,
    S3_INPUT_DIM,
    SEQUENCE_BATCH_CHUNKS,
    FeedForwardAblationPolicy,
    RecurrentAblationPolicy,
    SequenceBehaviorCloningGRU,
    build_mlp_examples,
    build_sequence_chunks,
)
from ..data.schema import OBSERVATION_DIM


@dataclass
class VariantTrainingResult:
    variant: str
    initialization_seed: int
    parameter_count: int
    updates: int
    history: list[dict[str, float | int | dict[str, object]]]
    checkpoints: dict[int, dict[str, torch.Tensor]]
    update_label_counts: list[int]


def make_model(variant: str) -> nn.Module:
    if variant == "S0":
        return BehaviorCloningMLP(input_dim=OBSERVATION_DIM)
    if variant == "S1":
        return BehaviorCloningMLP(input_dim=S1_INPUT_DIM)
    if variant == "S2":
        return SequenceBehaviorCloningGRU(
            input_dim=OBSERVATION_DIM,
            hidden_size=GRU_HIDDEN_SIZE,
        )
    if variant == "S3":
        return SequenceBehaviorCloningGRU(
            input_dim=S3_INPUT_DIM,
            hidden_size=GRU_HIDDEN_SIZE,
        )
    raise ValueError(f"未知 P4.1 variant：{variant!r}")


def make_policy(model: nn.Module, variant: str):
    if variant in {"S0", "S1"}:
        return FeedForwardAblationPolicy(model, variant=variant)
    if variant in {"S2", "S3"}:
        if not isinstance(model, SequenceBehaviorCloningGRU):
            raise TypeError("S2/S3 policy 必須使用 SequenceBehaviorCloningGRU。")
        return RecurrentAblationPolicy(model, variant=variant)
    raise ValueError(f"未知 P4.1 variant：{variant!r}")


def _sequence_tensors(dataset: P41Dataset, split: str, variant: str):
    chunks = build_sequence_chunks(
        dataset.episodes_for_split(split),
        variant=variant,
    )
    return (
        torch.as_tensor(np.stack([chunk.features for chunk in chunks]), dtype=torch.float32),
        torch.as_tensor(np.stack([chunk.actions for chunk in chunks]), dtype=torch.long),
        torch.as_tensor(np.stack([chunk.loss_mask for chunk in chunks]), dtype=torch.bool),
    )


def _mlp_tensors(dataset: P41Dataset, split: str, variant: str):
    features, labels, _targets = build_mlp_examples(
        dataset.episodes_for_split(split), variant=variant
    )
    return (
        torch.as_tensor(features, dtype=torch.float32),
        torch.as_tensor(labels, dtype=torch.long),
    )


def _classification_report(labels: torch.Tensor, predictions: torch.Tensor) -> dict[str, object]:
    confusion = torch.zeros((3, 3), dtype=torch.int64)
    for truth, prediction in zip(labels.cpu(), predictions.cpu()):
        confusion[int(truth), int(prediction)] += 1
    recalls = []
    for action in range(3):
        recalls.append(
            float(confusion[action, action] / max(1, int(confusion[action, :].sum())))
        )
    counts = Counter(int(value) for value in predictions.cpu().tolist())
    return {
        "records": int(len(labels)),
        "accuracy": float((labels == predictions).float().mean()),
        "confusion_matrix": confusion.tolist(),
        "recall": recalls,
        "predicted_action_counts": {str(action): counts[action] for action in range(3)},
    }


def offline_metrics(
    model: nn.Module,
    dataset: P41Dataset,
    *,
    split: str,
    variant: str,
    device: str | torch.device = "cpu",
) -> dict[str, object]:
    target_device = torch.device(device)
    model.to(target_device).eval()
    with torch.no_grad():
        if variant in {"S0", "S1"}:
            features, labels = _mlp_tensors(dataset, split, variant)
            features = features.to(target_device)
            labels = labels.to(target_device)
            logits = model(features)
        else:
            features, labels, loss_mask = _sequence_tensors(dataset, split, variant)
            features = features.to(target_device)
            labels = labels.to(target_device)
            loss_mask = loss_mask.to(target_device)
            if not isinstance(model, SequenceBehaviorCloningGRU):
                raise TypeError("S2/S3 必須使用 GRU model。")
            sequence_logits, _hidden = model(features)
            logits = sequence_logits[loss_mask]
            labels = labels[loss_mask]
        loss = nn.functional.cross_entropy(logits, labels)
        predictions = logits.argmax(dim=-1)
    return {
        "loss": float(loss),
        **_classification_report(labels, predictions),
    }


def _clone_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }


def train_variant(
    dataset: P41Dataset,
    *,
    variant: str,
    initialization_seed: int,
    max_updates: int,
    candidate_updates: Sequence[int],
    device: str | torch.device = "cpu",
    learning_rate: float = 1e-3,
) -> VariantTrainingResult:
    candidates = tuple(sorted({int(value) for value in candidate_updates}))
    if max_updates <= 0 or not candidates:
        raise ValueError("max updates 與 candidate updates 必須大於 0。")
    if candidates[0] <= 0 or candidates[-1] > max_updates:
        raise ValueError("candidate updates 必須位於 [1, max_updates]。")
    if candidates[-1] != max_updates:
        raise ValueError("最後一個 candidate update 必須等於 max_updates。")
    target_device = torch.device(device)
    torch.manual_seed(initialization_seed)
    np.random.seed(initialization_seed)
    model = make_model(variant).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    if variant in {"S0", "S1"}:
        train_features, train_labels = _mlp_tensors(dataset, "train", variant)
        loader = DataLoader(
            TensorDataset(train_features, train_labels),
            batch_size=min(MLP_BATCH_SIZE, len(train_labels)),
            shuffle=True,
            generator=torch.Generator().manual_seed(initialization_seed),
        )
    else:
        train_features, train_labels, train_mask = _sequence_tensors(
            dataset, "train", variant
        )
        loader = DataLoader(
            TensorDataset(train_features, train_labels, train_mask),
            # On the frozen 2,327-row train split, 168 chunks / 8 gives
            # exactly 21 updates per pass.  MLP batch 112 also gives 21,
            # so both consume every train label once per full pass.
            batch_size=min(SEQUENCE_BATCH_CHUNKS, len(train_features)),
            shuffle=True,
            generator=torch.Generator().manual_seed(initialization_seed),
        )

    iterator = iter(loader)
    history: list[dict[str, float | int | dict[str, object]]] = []
    checkpoints: dict[int, dict[str, torch.Tensor]] = {}
    update_label_counts: list[int] = []
    for update in range(1, max_updates + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            batch = next(iterator)
        model.train()
        optimizer.zero_grad()
        if variant in {"S0", "S1"}:
            features, labels = (item.to(target_device) for item in batch)
            logits = model(features)
        else:
            features, labels, loss_mask = (item.to(target_device) for item in batch)
            if not isinstance(model, SequenceBehaviorCloningGRU):
                raise TypeError("S2/S3 必須使用 GRU model。")
            sequence_logits, _hidden = model(features)
            logits = sequence_logits[loss_mask]
            labels = labels[loss_mask]
        update_label_counts.append(int(len(labels)))
        loss = nn.functional.cross_entropy(logits, labels)
        if not torch.isfinite(loss):
            raise RuntimeError(f"{variant} update {update} 出現非有限 loss。")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()
        if update in candidates:
            validation = offline_metrics(
                model,
                dataset,
                split="validation",
                variant=variant,
                device=target_device,
            )
            history.append(
                {
                    "update": update,
                    "train_loss": float(loss.detach()),
                    "validation_loss": float(validation["loss"]),
                    "validation": validation,
                }
            )
            checkpoints[update] = _clone_state(model)
    return VariantTrainingResult(
        variant=variant,
        initialization_seed=initialization_seed,
        parameter_count=sum(parameter.numel() for parameter in model.parameters()),
        updates=max_updates,
        history=history,
        checkpoints=checkpoints,
        update_label_counts=update_label_counts,
    )


def save_p41_checkpoint(
    path: str | Path,
    *,
    model: nn.Module,
    variant: str,
    initialization_seed: int,
    update: int,
    dataset_sha256: str,
) -> None:
    target = Path(path)
    if target.exists():
        raise FileExistsError(target)
    if len(dataset_sha256) != 64:
        raise ValueError("dataset sha256 必須是 64 字元。")
    target.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": P41_SCHEMA_VERSION,
            "variant": variant,
            "initialization_seed": int(initialization_seed),
            "update": int(update),
            "dataset_sha256": dataset_sha256,
            "model_state": _clone_state(model),
        },
        target,
    )


def load_p41_checkpoint(
    path: str | Path,
    *,
    expected_variant: str | None = None,
) -> tuple[nn.Module, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, Mapping) or payload.get("schema_version") != P41_SCHEMA_VERSION:
        raise ValueError("P4.1 checkpoint schema version 不符。")
    variant = str(payload.get("variant", ""))
    if expected_variant is not None and variant != expected_variant:
        raise ValueError(
            f"checkpoint variant {variant!r} 不符合預期 {expected_variant!r}。"
        )
    model = make_model(variant)
    state = payload.get("model_state")
    if not isinstance(state, Mapping):
        raise ValueError("checkpoint 缺少 model_state。")
    model.load_state_dict(state)
    metadata = {
        key: payload[key]
        for key in (
            "schema_version",
            "variant",
            "initialization_seed",
            "update",
            "dataset_sha256",
        )
    }
    return model.eval(), metadata


def selection_key(summary: Mapping[str, object], validation_loss: float, update: int) -> tuple:
    health = float(summary.get("health_death_rate", 0.0))
    return (
        not bool(summary.get("collapsed", True)),
        -health,
        -float(summary.get("bottom_death_rate", 1.0)),
        float(summary.get("deepest_floor_quantile_25", 0.0)),
        float(summary.get("deepest_floor_cvar25", 0.0)),
        float(summary.get("reach_rate_floor_10", 0.0)),
        -float(summary.get("direction_reversals_per_100_steps", float("inf"))),
        float(summary.get("median_deepest_floor", 0.0)),
        float(summary.get("mean_deepest_floor", 0.0)),
        -float(validation_loss),
        -int(update),
    )


def compare_to_s0_gate(
    candidate: Sequence[Mapping[str, object]],
    s0: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if len(candidate) != len(s0) or len(candidate) < 3:
        raise ValueError("P4.1 Gate 需要相同且至少 3 個 initialization summaries。")
    higher_metrics = {
        "q25": "deepest_floor_quantile_25",
        "cvar25": "deepest_floor_cvar25",
        "reach10": "reach_rate_floor_10",
    }
    lower_metrics = {
        "bottom": "bottom_death_rate",
        "oscillation": "direction_reversals_per_100_steps",
    }
    deltas: dict[str, list[float]] = {}
    for name, field in higher_metrics.items():
        deltas[name] = [
            float(current.get(field, 0.0)) - float(base.get(field, 0.0))
            for current, base in zip(candidate, s0)
        ]
    for name, field in lower_metrics.items():
        deltas[name] = [
            float(base.get(field, 0.0)) - float(current.get(field, 0.0))
            for current, base in zip(candidate, s0)
        ]
    means = {name: float(np.mean(values)) for name, values in deltas.items()}
    direction_checks = {
        f"{name}_nonnegative_at_least_2_of_3": sum(value >= -1e-9 for value in values) >= 2
        for name, values in deltas.items()
    }
    checks = {
        "three_initializations": len(candidate) >= 3,
        "no_action_collapse": all(not bool(item.get("collapsed", True)) for item in candidate),
        "health_safety_not_degraded": all(
            float(current.get("health_death_rate", 0.0)) == 0.0
            and float(current.get("health_death_rate", 0.0))
            <= float(base.get("health_death_rate", 0.0))
            for current, base in zip(candidate, s0)
        ),
        **direction_checks,
        "material_q25_improvement": means["q25"] >= 1.0,
        "material_cvar25_improvement": means["cvar25"] >= 0.5,
        "material_reach10_improvement": means["reach10"] >= 0.05,
        "material_bottom_improvement": means["bottom"] >= 0.025,
        "mean_oscillation_not_degraded": means["oscillation"] >= -1e-9,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "per_initialization_deltas": deltas,
        "mean_deltas": means,
        "thresholds": {
            "q25_floors": 1.0,
            "cvar25_floors": 0.5,
            "reach_floor_10_rate": 0.05,
            "bottom_death_rate": 0.025,
            "direction_reversals_per_100_steps": "mean non-regression",
            "consistent_initializations": "at least 2 of 3 nonnegative for every primary metric",
        },
    }


__all__ = [
    "VariantTrainingResult",
    "compare_to_s0_gate",
    "load_p41_checkpoint",
    "make_model",
    "make_policy",
    "offline_metrics",
    "save_p41_checkpoint",
    "selection_key",
    "train_variant",
]
