from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

import _common  # noqa: F401,E402
import torch

from stair_agent.learnability import (
    baseline_selector,
    evaluate_candidate,
    learned_selector,
)
from stair_agent.simulator.gates import evaluation_summary
from stair_agent.training.behavior_cloning import BCPolicy, BehaviorCloningMLP

from collect_spike_dagger0_corrections import spike_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-archive",
        type=Path,
        default=Path("../20260730T205104Z_spike_bc0.zip"),
    )
    parser.add_argument("--eval-seed-start", type=int, default=1500)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/spike_bc0_frozen_eval_1500.json"),
    )
    args = parser.parse_args()
    seeds = tuple(range(args.eval_seed_start, args.eval_seed_start + 20))
    config = spike_config()
    evaluations = {}
    selected_epochs = {}
    with zipfile.ZipFile(args.source_archive) as archive:
        used_seeds = set()
        for initialization_seed in (0, 1, 2):
            summary = json.loads(
                archive.read(
                    f"spike_bc0_colab_seed_{initialization_seed}_smoke_summary.json"
                )
            )
            for values in summary["seed_partitions"].values():
                used_seeds.update(values)
            selected_epochs[str(initialization_seed)] = int(
                summary["selected_epoch"]
            )
            state = torch.load(
                io.BytesIO(
                    archive.read(
                        f"spike_bc0_colab_seed_{initialization_seed}_model.pt"
                    )
                ),
                map_location="cpu",
                weights_only=True,
            )
            model = BehaviorCloningMLP()
            model.load_state_dict(state)
            evaluations[f"bc0_seed_{initialization_seed}"] = evaluation_summary(
                evaluate_candidate(
                    f"bc0_seed_{initialization_seed}",
                    learned_selector(BCPolicy(model)),
                    seeds=seeds,
                    max_episode_steps=600,
                    config=config,
                )
            )
    overlap = sorted(set(seeds) & used_seeds)
    if overlap:
        raise RuntimeError(f"frozen comparison seeds 與舊實驗重疊：{overlap}")
    evaluations["baseline"] = evaluation_summary(
        evaluate_candidate(
            "baseline",
            baseline_selector(),
            seeds=seeds,
            max_episode_steps=600,
            config=config,
        )
    )
    output = {
        "experiment": "spike-bc0-frozen-comparison-v0",
        "source_archive": str(args.source_archive),
        "selected_epochs": selected_epochs,
        "eval_seeds": list(seeds),
        "evaluations": evaluations,
        "mean_bc_floors": sum(
            evaluations[f"bc0_seed_{seed}"]["mean_floors"]
            for seed in range(3)
        )
        / 3,
        "baseline_mean_floors": evaluations["baseline"]["mean_floors"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "eval_seeds": output["eval_seeds"],
                "floors": {
                    key: value["mean_floors"]
                    for key, value in evaluations.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
