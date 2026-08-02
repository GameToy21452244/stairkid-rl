from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np


def main() -> int:
    root = Path("artifacts")
    frozen = json.loads(
        (root / "spike_bc0_frozen_eval_1500.json").read_text(encoding="utf-8")
    )
    summaries = [
        json.loads(
            (root / f"spike_dagger0_seed_{seed}_smoke_summary.json").read_text(
                encoding="utf-8"
            )
        )
        for seed in range(3)
    ]
    seed_results = []
    old_terminals: Counter[str] = Counter()
    dagger_terminals: Counter[str] = Counter()
    for seed, summary in enumerate(summaries):
        old = frozen["evaluations"][f"bc0_seed_{seed}"]
        dagger = summary["evaluations"]["bc0"]
        old_terminals.update(old["terminal_reasons"])
        dagger_terminals.update(dagger["terminal_reasons"])
        old_by_seed = {
            item["seed"]: item["floors"] for item in old["episode_results"]
        }
        dagger_by_seed = {
            item["seed"]: item["floors"] for item in dagger["episode_results"]
        }
        paired = [
            dagger_by_seed[environment_seed] - old_by_seed[environment_seed]
            for environment_seed in sorted(old_by_seed)
        ]
        seed_results.append(
            {
                "initialization_seed": seed,
                "selected_epoch": summary["selected_epoch"],
                "final_gate_passed": summary["gate"]["passed"],
                "old_bc_mean_floors": old["mean_floors"],
                "dagger_mean_floors": dagger["mean_floors"],
                "mean_floor_delta": dagger["mean_floors"] - old["mean_floors"],
                "old_success_rate_floor_10": old["success_rate_floor_10"],
                "dagger_success_rate_floor_10": dagger["success_rate_floor_10"],
                "dagger_terminal_reasons": dagger["terminal_reasons"],
                "dagger_collapsed": dagger["collapsed"],
                "paired_wins": sum(value > 0 for value in paired),
                "paired_ties": sum(value == 0 for value in paired),
                "paired_losses": sum(value < 0 for value in paired),
                "paired_median_delta": float(np.median(paired)),
            }
        )
    old_mean = float(np.mean([item["old_bc_mean_floors"] for item in seed_results]))
    dagger_mean = float(np.mean([item["dagger_mean_floors"] for item in seed_results]))
    output = {
        "experiment": "spike-dagger0-balanced-v0",
        "eval_seeds": frozen["eval_seeds"],
        "seed_results": seed_results,
        "aggregate": {
            "old_bc_mean_floors": old_mean,
            "dagger_mean_floors": dagger_mean,
            "mean_floor_delta": dagger_mean - old_mean,
            "old_success_rate_floor_10": float(
                np.mean(
                    [item["old_success_rate_floor_10"] for item in seed_results]
                )
            ),
            "dagger_success_rate_floor_10": float(
                np.mean(
                    [item["dagger_success_rate_floor_10"] for item in seed_results]
                )
            ),
            "old_terminal_reasons": dict(old_terminals),
            "dagger_terminal_reasons": dict(dagger_terminals),
        },
        "gate": {
            "passed": all(item["final_gate_passed"] for item in seed_results),
            "completed_initialization_seeds": len(seed_results),
            "criteria": (
                "3/3 final rollout gates pass, no collapse, no health deaths; "
                "final seeds are not reused after this decision"
            ),
            "dagger_rounds_started": 1,
            "additional_round_allowed": False,
        },
    }
    target = root / "spike_dagger0_gate_summary.json"
    target.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["gate"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
