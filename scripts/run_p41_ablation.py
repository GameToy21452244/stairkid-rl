from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

import _common  # noqa: F401,E402
import numpy as np
import torch

from stair_agent.learnability import evaluate_candidate, learned_selector
from stair_agent.simulator.gates import evaluation_summary
from stair_agent.simulator.state import ShaftEnvConfig
from stair_agent.training.p41_ablation import (
    compare_to_s0_gate,
    load_p41_checkpoint,
    make_model,
    make_policy,
    offline_metrics,
    save_p41_checkpoint,
    selection_key,
    train_variant,
)
from stair_agent.training.p41_sequence import (
    CANDIDATE_UPDATES,
    FINAL_SEEDS,
    INITIALIZATION_SEEDS,
    MAX_EPISODE_STEPS,
    MAX_UPDATES,
    P41_VARIANTS,
    SELECTION_SEEDS,
    build_experiment_manifest,
    load_p41_teacher_dataset,
)


LOCAL_SMOKE_SEEDS = (3900, 3901)


def _device(value: str) -> torch.device:
    if value == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    result = torch.device(value)
    if result.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("要求 CUDA，但目前 runtime 無可用 CUDA device。")
    return result


def _simulator_config() -> ShaftEnvConfig:
    return ShaftEnvConfig(
        distribution="easy",
        fps=10,
        enable_health=True,
        enable_spikes=True,
        spike_spawn_probability=0.10,
        initial_safe_normal_platforms=3,
        minimum_normal_platforms_between_spikes=5,
    )


def _write_json_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"拒絕覆寫既有 P4.1 artifact：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _freeze_manifest(path: Path, payload: Mapping[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != payload:
            raise ValueError(
                f"既有 manifest 與目前資料/protocol 不一致，拒絕靜默改寫：{path}"
            )
        return "MATCHED_EXISTING"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return "CREATED"


def _model_with_state(variant: str, state: Mapping[str, torch.Tensor], device: torch.device):
    model = make_model(variant).to(device)
    model.load_state_dict(state)
    return model.eval()


def _rollout(
    model: torch.nn.Module,
    *,
    variant: str,
    seeds,
    max_episode_steps: int,
) -> dict[str, object]:
    policy = make_policy(model, variant)
    return evaluation_summary(
        evaluate_candidate(
            f"p41-{variant}",
            learned_selector(policy),
            seeds=seeds,
            max_episode_steps=max_episode_steps,
            config=_simulator_config(),
        )
    )


def run_interface_smoke(
    *,
    dataset,
    manifest: Mapping[str, object],
    device: torch.device,
) -> dict[str, object]:
    results: dict[str, object] = {}
    checks: dict[str, bool] = {}
    dataset_sha = str(manifest["dataset"]["sha256"])
    for variant in P41_VARIANTS:
        training = train_variant(
            dataset,
            variant=variant,
            initialization_seed=0,
            max_updates=4,
            candidate_updates=(2, 4),
            device=device,
        )
        state = training.checkpoints[4]
        model = _model_with_state(variant, state, device)
        checkpoint_round_trip = False
        with TemporaryDirectory(prefix="p41-checkpoint-") as directory:
            checkpoint = Path(directory) / f"{variant}.pt"
            save_p41_checkpoint(
                checkpoint,
                model=model,
                variant=variant,
                initialization_seed=0,
                update=4,
                dataset_sha256=dataset_sha,
            )
            restored, metadata = load_p41_checkpoint(
                checkpoint,
                expected_variant=variant,
            )
            restored.to(device)
            checkpoint_round_trip = (
                metadata["dataset_sha256"] == dataset_sha
                and int(metadata["update"]) == 4
            )
            model = restored
        test_metrics = offline_metrics(
            model,
            dataset,
            split="test",
            variant=variant,
            device=device,
        )
        rollout = _rollout(
            model,
            variant=variant,
            seeds=LOCAL_SMOKE_SEEDS,
            max_episode_steps=120,
        )
        finite = all(
            np.isfinite(float(item["validation_loss"]))
            for item in training.history
        ) and np.isfinite(float(test_metrics["loss"]))
        checks[f"{variant}_finite_training"] = bool(finite)
        checks[f"{variant}_checkpoint_round_trip"] = checkpoint_round_trip
        checks[f"{variant}_two_closed_loop_episodes"] = int(rollout["episodes"]) == 2
        results[variant] = {
            "parameter_count": training.parameter_count,
            "updates": training.updates,
            "labels_per_update": {
                "minimum": min(training.update_label_counts),
                "maximum": max(training.update_label_counts),
                "mean": float(np.mean(training.update_label_counts)),
            },
            "history": training.history,
            "test_classification": test_metrics,
            "closed_loop_development_smoke": rollout,
        }
    return {
        "experiment": "P4.1-local-interface-smoke-v1",
        "status": "INTERFACE_PASS" if all(checks.values()) else "ENGINEERING_FAIL_STOP",
        "scientific_gate_evaluated": False,
        "device": str(device),
        "manifest_schema_version": manifest["schema_version"],
        "dataset_sha256": dataset_sha,
        "dataset_records": manifest["dataset"]["records"],
        "development_seeds": list(LOCAL_SMOKE_SEEDS),
        "retired_seed_note": "development interface only; never selection or final",
        "checks": checks,
        "models": results,
        "next_stage": (
            "READY_FOR_BOUNDED_COLAB_ABLATION"
            if all(checks.values())
            else "STOP_FIX_LOCAL_INTERFACE"
        ),
    }


def _mean(summary_items, field: str) -> float:
    return float(np.mean([float(item[field]) for item in summary_items]))


def _architecture_rank(summary_items, gate: Mapping[str, object]) -> tuple:
    return (
        bool(gate["passed"]),
        _mean(summary_items, "reach_rate_floor_10"),
        -_mean(summary_items, "bottom_death_rate"),
        _mean(summary_items, "deepest_floor_quantile_25"),
        _mean(summary_items, "deepest_floor_cvar25"),
        -_mean(summary_items, "direction_switches_per_100_steps"),
        _mean(summary_items, "median_deepest_floor"),
        _mean(summary_items, "mean_deepest_floor"),
    )


def run_colab_ablation(
    *,
    dataset,
    manifest: Mapping[str, object],
    device: torch.device,
    output_dir: Path,
) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(f"拒絕覆寫既有 P4.1 output dir：{output_dir}")
    output_dir.mkdir(parents=True)
    dataset_sha = str(manifest["dataset"]["sha256"])
    selected_states: dict[tuple[str, int], dict[str, torch.Tensor]] = {}
    training_records: dict[str, list[dict[str, object]]] = {
        variant: [] for variant in P41_VARIANTS
    }
    selection_summaries: dict[str, list[dict[str, object]]] = {
        variant: [] for variant in P41_VARIANTS
    }

    for variant in P41_VARIANTS:
        for initialization_seed in INITIALIZATION_SEEDS:
            training = train_variant(
                dataset,
                variant=variant,
                initialization_seed=initialization_seed,
                max_updates=MAX_UPDATES,
                candidate_updates=CANDIDATE_UPDATES,
                device=device,
            )
            candidates: list[dict[str, object]] = []
            for update in CANDIDATE_UPDATES:
                model = _model_with_state(
                    variant,
                    training.checkpoints[update],
                    device,
                )
                rollout = _rollout(
                    model,
                    variant=variant,
                    seeds=SELECTION_SEEDS,
                    max_episode_steps=MAX_EPISODE_STEPS,
                )
                validation = next(
                    item for item in training.history if int(item["update"]) == update
                )
                rank = selection_key(
                    rollout,
                    float(validation["validation_loss"]),
                    update,
                )
                candidates.append(
                    {
                        "update": update,
                        "validation": validation["validation"],
                        "selection_rollout": rollout,
                        "selection_rank": list(rank),
                    }
                )
            selected = max(candidates, key=lambda item: tuple(item["selection_rank"]))
            selected_update = int(selected["update"])
            selected_states[(variant, initialization_seed)] = training.checkpoints[
                selected_update
            ]
            selection_summaries[variant].append(selected["selection_rollout"])
            selected_model = _model_with_state(
                variant,
                training.checkpoints[selected_update],
                device,
            )
            test_metrics = offline_metrics(
                selected_model,
                dataset,
                split="test",
                variant=variant,
                device=device,
            )
            training_records[variant].append(
                {
                    "initialization_seed": initialization_seed,
                    "parameter_count": training.parameter_count,
                    "update_label_counts": training.update_label_counts,
                    "selected_update": selected_update,
                    "candidates": candidates,
                    "test_classification": test_metrics,
                }
            )

    selection_gates = {
        variant: compare_to_s0_gate(
            selection_summaries[variant], selection_summaries["S0"]
        )
        for variant in ("S1", "S2", "S3")
    }
    eligible = [variant for variant, gate in selection_gates.items() if gate["passed"]]
    selected_architecture = (
        max(
            eligible,
            key=lambda variant: _architecture_rank(
                selection_summaries[variant], selection_gates[variant]
            ),
        )
        if eligible
        else None
    )

    for variant in P41_VARIANTS:
        for initialization_seed in INITIALIZATION_SEEDS:
            update = int(
                training_records[variant][initialization_seed]["selected_update"]
            )
            model = _model_with_state(
                variant,
                selected_states[(variant, initialization_seed)],
                torch.device("cpu"),
            )
            save_p41_checkpoint(
                output_dir / f"{variant.lower()}_seed_{initialization_seed}_selected.pt",
                model=model,
                variant=variant,
                initialization_seed=initialization_seed,
                update=update,
                dataset_sha256=dataset_sha,
            )

    final_summaries: dict[str, list[dict[str, object]]] = {}
    final_gate = None
    if selected_architecture is not None:
        for variant in ("S0", selected_architecture):
            final_summaries[variant] = []
            for initialization_seed in INITIALIZATION_SEEDS:
                model = _model_with_state(
                    variant,
                    selected_states[(variant, initialization_seed)],
                    device,
                )
                final_summaries[variant].append(
                    _rollout(
                        model,
                        variant=variant,
                        seeds=FINAL_SEEDS,
                        max_episode_steps=MAX_EPISODE_STEPS,
                    )
                )
        final_gate = compare_to_s0_gate(
            final_summaries[selected_architecture],
            final_summaries["S0"],
        )

    if selected_architecture is None:
        status = "FAIL_STOP_SELECTION"
        next_stage = "STOP_REVIEW_CAUSAL_SCHEMA_SEQUENCE_LENGTH_OR_DATA_COVERAGE"
    elif final_gate and final_gate["passed"]:
        status = "PASS"
        next_stage = "P4.2_RARE_BRANCH_SEQUENCE_DATASET"
    else:
        status = "FAIL_STOP_FINAL"
        next_stage = "STOP_REVIEW_GENERALIZATION_BEFORE_P4.2"
    return {
        "experiment": "P4.1-bounded-S0-S1-S2-S3-ablation-v1",
        "status": status,
        "device": str(device),
        "manifest": manifest,
        "training": training_records,
        "selection_summaries": selection_summaries,
        "selection_gates_vs_s0": selection_gates,
        "selected_architecture": selected_architecture,
        "final_summaries": final_summaries,
        "final_gate_vs_s0": final_gate,
        "next_stage": next_stage,
        "scientific_fail_returns_zero": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("artifacts/spike_teacher_dataset_v1.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/p41_experiment_manifest.json"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--interface-smoke", action="store_true")
    mode.add_argument("--execute-colab", action="store_true")
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--smoke-output",
        type=Path,
        default=Path("artifacts/p41_local_interface_smoke.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/p41_colab_ablation_v1"),
    )
    args = parser.parse_args()

    dataset = load_p41_teacher_dataset(args.dataset)
    manifest = build_experiment_manifest(args.dataset, dataset)
    manifest_state = _freeze_manifest(args.manifest, manifest)
    print(f"P4.1 manifest: {manifest_state} -> {args.manifest.resolve()}")
    print(
        f"dataset: {manifest['dataset']['episodes']} episodes / "
        f"{manifest['dataset']['records']} records"
    )
    if not args.interface_smoke and not args.execute_colab:
        print("PRECHECK PASS：未訓練。下一步可明示 --interface-smoke。")
        return 0

    device = _device(args.device)
    if args.interface_smoke:
        output = run_interface_smoke(
            dataset=dataset,
            manifest=manifest,
            device=device,
        )
        _write_json_exclusive(args.smoke_output, output)
        print(json.dumps({
            "status": output["status"],
            "next_stage": output["next_stage"],
            "artifact": str(args.smoke_output.resolve()),
        }, ensure_ascii=False, indent=2))
        return 0 if output["status"] == "INTERFACE_PASS" else 2

    output = run_colab_ablation(
        dataset=dataset,
        manifest=manifest,
        device=device,
        output_dir=args.output_dir,
    )
    summary_path = args.output_dir / "p41_ablation_summary.json"
    summary_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": output["status"],
        "selected_architecture": output["selected_architecture"],
        "next_stage": output["next_stage"],
        "artifact": str(summary_path.resolve()),
    }, ensure_ascii=False, indent=2))
    # A scientific FAIL is a valid, reportable experiment outcome.  Reserve
    # non-zero exits for engineering/runtime failures so Colab keeps the JSON.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
