from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import _common  # noqa: F401,E402
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from stair_agent.learnability import (
    baseline_selector,
    evaluate_candidate,
    learned_selector,
    random_selector,
    release_selector,
)
from stair_agent.simulator.gates import evaluation_summary
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.behavior_cloning import BCPolicy, BehaviorCloningMLP
from stair_agent.training.bc_checkpoint_selection import (
    checkpoint_gate_passed,
    checkpoint_selection_key,
    ensure_disjoint_seed_partitions,
)


def load_rows(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def tensors(rows):
    x = torch.tensor([row["observation"] for row in rows], dtype=torch.float32)
    y = torch.tensor([row["soft_target"] for row in rows], dtype=torch.float32)
    labels = torch.tensor([row["action"] for row in rows], dtype=torch.long)
    return x, y, labels


def classification_metrics(model, rows):
    x, _soft, labels = tensors(rows)
    with torch.no_grad():
        predictions = model(x).argmax(dim=1)
    confusion = torch.zeros((3, 3), dtype=torch.int64)
    for truth, prediction in zip(labels, predictions):
        confusion[truth, prediction] += 1
    precision = []
    recall = []
    for action in range(3):
        tp = int(confusion[action, action])
        precision.append(tp / max(1, int(confusion[:, action].sum())))
        recall.append(tp / max(1, int(confusion[action, :].sum())))
    counts = Counter(int(value) for value in predictions.tolist())
    return {
        "accuracy": float((predictions == labels).float().mean()),
        "confusion_matrix": confusion.tolist(),
        "precision": precision,
        "recall": recall,
        "predicted_action_counts": {str(i): counts.get(i, 0) for i in range(3)},
    }


def classification_metrics_for_kind(model, rows, kind):
    subset = [
        row for row in rows if row.get("target_platform_kind") == kind
    ]
    if not subset:
        return {"records": 0, "accuracy": None}
    metrics = classification_metrics(model, subset)
    return {"records": len(subset), **metrics}


def classification_metrics_with_visible_kind(model, rows, kind):
    subset = [
        row
        for row in rows
        if kind in row.get("visible_platform_kinds", [])
    ]
    if not subset:
        return {"records": 0, "accuracy": None}
    metrics = classification_metrics(model, subset)
    return {"records": len(subset), **metrics}


def simulator_config(curriculum: str) -> ShaftEnvConfig:
    if curriculum == "plain":
        return ShaftEnvConfig(distribution="easy", fps=10)
    if curriculum == "spike-v0":
        return ShaftEnvConfig(
            distribution="easy",
            fps=10,
            enable_health=True,
            enable_spikes=True,
            spike_spawn_probability=0.10,
            initial_safe_normal_platforms=3,
            minimum_normal_platforms_between_spikes=5,
        )
    raise ValueError(f"未知 curriculum：{curriculum}")


def parse_candidate_epochs(value: str, *, max_epochs: int) -> tuple[int, ...]:
    requested = sorted(
        {
            int(item.strip())
            for item in value.split(",")
            if item.strip()
        }
    )
    if not requested or any(epoch <= 0 for epoch in requested):
        raise ValueError("candidate epochs 必須是以逗號分隔的正整數。")
    bounded = [epoch for epoch in requested if epoch <= max_epochs]
    if max_epochs not in bounded and max_epochs < max(requested):
        bounded.append(max_epochs)
    if not bounded:
        raise ValueError("沒有 candidate epoch 落在 max-epochs 範圍內。")
    return tuple(sorted(set(bounded)))


def evaluate_references(config, seeds):
    return {
        "baseline": evaluation_summary(
            evaluate_candidate(
                "baseline",
                baseline_selector(),
                seeds=seeds,
                max_episode_steps=600,
                config=config,
            )
        ),
        "random": evaluation_summary(
            evaluate_candidate(
                "random",
                random_selector,
                seeds=seeds,
                max_episode_steps=600,
                config=config,
            )
        ),
        "release": evaluation_summary(
            evaluate_candidate(
                "release",
                release_selector,
                seeds=seeds,
                max_episode_steps=600,
                config=config,
            )
        ),
    }


def evaluate_model(model, config, seeds):
    return evaluation_summary(
        evaluate_candidate(
            "bc0",
            learned_selector(BCPolicy(model)),
            seeds=seeds,
            max_episode_steps=600,
            config=config,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("artifacts/teacher_dataset_v0.jsonl"))
    parser.add_argument("--loss", choices=("soft", "hard"), default="hard")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-epochs", type=int, default=30)
    parser.add_argument("--output-prefix", default="bc0")
    parser.add_argument(
        "--curriculum",
        choices=("plain", "spike-v0"),
        default="plain",
    )
    parser.add_argument(
        "--candidate-epochs",
        default="3,5,8,11,14,17",
        help="以逗號分隔、預先固定的 rollout 選模 epoch。",
    )
    parser.add_argument("--selection-seed-start", type=int, default=1060)
    parser.add_argument("--final-eval-seed-start", type=int, default=1200)
    parser.add_argument(
        "--retired-diagnostic-seed-start",
        type=int,
        default=1100,
    )
    parser.add_argument(
        "--retired-diagnostic-seed-count",
        type=int,
        default=20,
    )
    args = parser.parse_args()
    if args.max_epochs <= 0:
        parser.error("--max-epochs 必須大於 0。")
    if args.retired_diagnostic_seed_count < 0:
        parser.error("--retired-diagnostic-seed-count 不可小於 0。")
    try:
        candidate_epochs = parse_candidate_epochs(
            args.candidate_epochs,
            max_epochs=args.max_epochs,
        )
    except ValueError as exc:
        parser.error(str(exc))
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    source = args.dataset
    if not source.exists():
        raise SystemExit("teacher dataset 不存在；不得跳過前置 gate。")
    rows = load_rows(source)
    train = [row for row in rows if row["split"] == "train"]
    validation = [row for row in rows if row["split"] == "validation"]
    test = [row for row in rows if row["split"] == "test"]
    dataset_seeds = sorted({int(row["seed"]) for row in rows})
    selection_seeds = tuple(
        range(args.selection_seed_start, args.selection_seed_start + 20)
    )
    final_seeds = tuple(
        range(args.final_eval_seed_start, args.final_eval_seed_start + 20)
    )
    try:
        ensure_disjoint_seed_partitions(
            dataset_seeds=dataset_seeds,
            selection_seeds=selection_seeds,
            final_seeds=final_seeds,
        )
    except ValueError as exc:
        parser.error(str(exc))
    train_x, train_soft, train_labels = tensors(train)
    val_x, val_soft, val_labels = tensors(validation)
    loader = DataLoader(
        TensorDataset(train_x, train_soft, train_labels),
        batch_size=128,
        shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
    )
    model = BehaviorCloningMLP()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    history = []
    candidate_states = {}
    for epoch in range(1, max(candidate_epochs) + 1):
        model.train()
        total = 0.0
        for observations, targets, labels in loader:
            optimizer.zero_grad()
            logits = model(observations)
            if args.loss == "soft":
                loss = -(targets * torch.log_softmax(logits, dim=1)).sum(dim=1).mean()
            else:
                loss = nn.functional.cross_entropy(logits, labels)
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(observations)
        model.eval()
        with torch.no_grad():
            if args.loss == "soft":
                val_loss = float(
                    -(val_soft * torch.log_softmax(model(val_x), dim=1)).sum(dim=1).mean()
                )
            else:
                val_loss = float(
                    nn.functional.cross_entropy(model(val_x), val_labels)
                )
        history.append(
            {"epoch": epoch, "train_loss": total / len(train), "validation_loss": val_loss}
        )
        if epoch in candidate_epochs:
            candidate_states[epoch] = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }

    config = simulator_config(args.curriculum)
    selection_references = evaluate_references(config, selection_seeds)
    candidate_results = []
    output_base = Path("artifacts")
    for epoch in candidate_epochs:
        model.load_state_dict(candidate_states[epoch])
        model.eval()
        offline_metrics = classification_metrics(model, test)
        selection_evaluation = evaluate_model(
            model,
            config,
            selection_seeds,
        )
        validation_loss = history[epoch - 1]["validation_loss"]
        passed_selection_gate = checkpoint_gate_passed(
            evaluation=selection_evaluation,
            baseline=selection_references["baseline"],
            random=selection_references["random"],
            release=selection_references["release"],
            curriculum=args.curriculum,
        )
        rank = checkpoint_selection_key(
            epoch=epoch,
            validation_loss=validation_loss,
            evaluation=selection_evaluation,
            baseline=selection_references["baseline"],
            random=selection_references["random"],
            release=selection_references["release"],
            curriculum=args.curriculum,
        )
        checkpoint_path = (
            output_base / f"{args.output_prefix}_epoch_{epoch}_model.pt"
        )
        torch.save(candidate_states[epoch], checkpoint_path)
        candidate_results.append(
            {
                "epoch": epoch,
                "validation_loss": validation_loss,
                "test_classification": offline_metrics,
                "selection_evaluation": selection_evaluation,
                "selection_gate_passed": passed_selection_gate,
                "selection_rank": list(rank),
                "checkpoint": str(checkpoint_path),
            }
        )

    selected = max(
        candidate_results,
        key=lambda item: tuple(item["selection_rank"]),
    )
    selected_epoch = int(selected["epoch"])
    model.load_state_dict(candidate_states[selected_epoch])
    model.eval()
    metrics = classification_metrics(model, test)
    final_references = evaluate_references(config, final_seeds)
    final_bc = evaluate_model(model, config, final_seeds)
    evaluations = {"bc0": final_bc, **final_references}
    passed = checkpoint_gate_passed(
        evaluation=final_bc,
        baseline=final_references["baseline"],
        random=final_references["random"],
        release=final_references["release"],
        curriculum=args.curriculum,
    )
    output = {
        "experiment": "BC0-rollout-selected-v2",
        "seed": args.seed,
        "loss": args.loss,
        "dataset": str(source),
        "curriculum": args.curriculum,
        "environment_version": config.effective_environment_version,
        "seed_partitions": {
            "dataset": dataset_seeds,
            "checkpoint_selection": list(selection_seeds),
            "final_evaluation": list(final_seeds),
            "retired_diagnostic": list(
                range(
                    args.retired_diagnostic_seed_start,
                    args.retired_diagnostic_seed_start
                    + args.retired_diagnostic_seed_count,
                )
            ),
        },
        "candidate_epochs": list(candidate_epochs),
        "selected_epoch": selected_epoch,
        "architecture": [268, 256, 128, 3],
        "train_records": len(train),
        "validation_records": len(validation),
        "test_records": len(test),
        "history": history,
        "test_classification": metrics,
        "checkpoint_selection": {
            "criterion": (
                "safe/non-collapsed first, then reach-floor-10, fewer "
                "bottom deaths, deepest-floor Q25/median, rollout gate, "
                "mean deepest floor, validation loss, earlier epoch"
            ),
            "references": selection_references,
            "candidates": candidate_results,
            "selected_epoch": selected_epoch,
        },
        "spike_target_classification": (
            classification_metrics_for_kind(model, test, "spikes")
        ),
        "spike_visible_classification": (
            classification_metrics_with_visible_kind(
                model, test, "spikes"
            )
        ),
        "evaluations": evaluations,
        "gate": {
            "passed": passed,
            "criteria": (
                "selected only on checkpoint-selection seeds; final seeds: "
                "not collapsed, >random/release, >=80% baseline deepest "
                "mean/Q25, >=90% baseline reach-floor-10, bottom deaths "
                "<= baseline, "
                "spike-v0 has 0 health deaths"
            ),
        },
    }
    Path(f"artifacts/{args.output_prefix}_smoke_summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    torch.save(model.state_dict(), f"artifacts/{args.output_prefix}_model.pt")
    print(json.dumps({
        "selected_epoch": selected_epoch,
        "selection_mean_deepest_floors": {
            item["epoch"]: item["selection_evaluation"][
                "mean_deepest_floor"
            ]
            for item in candidate_results
        },
        "gate": output["gate"],
        "classification": metrics,
        "final_mean_deepest_floors": {
            key: value["mean_deepest_floor"]
            for key, value in evaluations.items()
        },
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
