from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

import numpy as np

from _common import PROJECT_ROOT, run_main
from run_learnability_probe import (
    EVAL_SEEDS,
    MAX_EVAL_EPISODE_STEPS,
    repository_fingerprint,
    train_dqn,
    train_ppo,
)
from stair_agent.learnability import (
    baseline_selector,
    evaluate_candidate,
    learned_selector,
    random_selector,
    release_selector,
)


EXPERIMENT_ID = "sim_learnability_p1_v1"
TRAIN_SEEDS = [31_011, 31_012, 31_013]
TOTAL_TIMESTEPS = 8_192
MAX_TRAIN_SECONDS = 60.0
MIN_DIRECTION_SHARE = 0.02
MIN_FLOOR_ADVANTAGE = 0.2


def main() -> None:
    import stable_baselines3
    import torch

    model_dir = PROJECT_ROOT / "models" / "probes" / EXPERIMENT_ID
    report_json = (
        PROJECT_ROOT / "reports" / "SIM_LEARNABILITY_PROBE_P1_V1.json"
    )
    report_md = (
        PROJECT_ROOT / "reports" / "SIM_LEARNABILITY_PROBE_P1_V1.md"
    )
    for path in (model_dir, report_json, report_md):
        if path.exists():
            raise FileExistsError(f"拒絕覆寫既有 P1 artifact：{path}")
    model_dir.mkdir(parents=True)

    baselines = {
        "random": evaluate_candidate(
            "random",
            random_selector,
            seeds=EVAL_SEEDS,
            max_episode_steps=MAX_EVAL_EPISODE_STEPS,
        ),
        "release": evaluate_candidate(
            "release",
            release_selector,
            seeds=EVAL_SEEDS,
            max_episode_steps=MAX_EVAL_EPISODE_STEPS,
        ),
        "baseline": evaluate_candidate(
            "baseline",
            baseline_selector(),
            seeds=EVAL_SEEDS,
            max_episode_steps=MAX_EVAL_EPISODE_STEPS,
        ),
    }
    training: dict[str, list[dict]] = {"ppo": [], "sb3_dqn": []}
    evaluations: dict[str, list] = {"ppo": [], "sb3_dqn": []}
    for train_seed in TRAIN_SEEDS:
        ppo_model, ppo_training = train_ppo(
            model_dir / f"ppo_seed_{train_seed}",
            train_seed=train_seed,
            total_timesteps=TOTAL_TIMESTEPS,
            max_train_seconds=MAX_TRAIN_SECONDS,
        )
        dqn_model, dqn_training = train_dqn(
            model_dir / f"dqn_seed_{train_seed}",
            train_seed=train_seed,
            total_timesteps=TOTAL_TIMESTEPS,
            max_train_seconds=MAX_TRAIN_SECONDS,
        )
        ppo_training["train_seed"] = train_seed
        dqn_training["train_seed"] = train_seed
        training["ppo"].append(ppo_training)
        training["sb3_dqn"].append(dqn_training)
        evaluations["ppo"].append(
            evaluate_candidate(
                f"ppo_seed_{train_seed}",
                learned_selector(ppo_model),
                seeds=EVAL_SEEDS,
                max_episode_steps=MAX_EVAL_EPISODE_STEPS,
            )
        )
        evaluations["sb3_dqn"].append(
            evaluate_candidate(
                f"sb3_dqn_seed_{train_seed}",
                learned_selector(dqn_model),
                seeds=EVAL_SEEDS,
                max_episode_steps=MAX_EVAL_EPISODE_STEPS,
            )
        )

    random_result = baselines["random"]
    algorithm_gates = {}
    per_seed_gates = {}
    for algorithm, results in evaluations.items():
        seed_gates = []
        for train_seed, result in zip(TRAIN_SEEDS, results):
            shares = {
                name: count / max(1, result.total_steps)
                for name, count in result.action_counts.items()
            }
            gate = {
                "train_seed": train_seed,
                "no_action_collapse": not result.collapsed,
                "left_share_ge_0_02": (
                    shares["LEFT"] >= MIN_DIRECTION_SHARE
                ),
                "right_share_ge_0_02": (
                    shares["RIGHT"] >= MIN_DIRECTION_SHARE
                ),
                "mean_floors_ge_random": (
                    result.mean_floors >= random_result.mean_floors
                ),
                "mean_return_ge_random": (
                    result.mean_return >= random_result.mean_return
                ),
            }
            gate["seed_pass"] = all(
                value
                for key, value in gate.items()
                if key != "train_seed"
            )
            seed_gates.append(gate)
        mean_floors = float(np.mean([r.mean_floors for r in results]))
        mean_return = float(np.mean([r.mean_return for r in results]))
        algorithm_gate = {
            "all_seeds_no_action_collapse": all(
                not result.collapsed for result in results
            ),
            "at_least_two_seed_passes": (
                sum(gate["seed_pass"] for gate in seed_gates) >= 2
            ),
            "mean_floors_ge_random_plus_0_2": (
                mean_floors
                >= random_result.mean_floors + MIN_FLOOR_ADVANTAGE
            ),
            "mean_return_ge_random": (
                mean_return >= random_result.mean_return
            ),
        }
        algorithm_gate["algorithm_pass"] = all(algorithm_gate.values())
        algorithm_gate["mean_floors"] = mean_floors
        algorithm_gate["mean_return"] = mean_return
        per_seed_gates[algorithm] = seed_gates
        algorithm_gates[algorithm] = algorithm_gate

    gates = {
        "baseline_mean_floors_gt_random": (
            baselines["baseline"].mean_floors > random_result.mean_floors
        ),
        "all_training_runs_completed": all(
            run["actual_timesteps"] == TOTAL_TIMESTEPS
            for runs in training.values()
            for run in runs
        ),
        "at_least_one_algorithm_pass": any(
            gate["algorithm_pass"] for gate in algorithm_gates.values()
        ),
    }
    payload = {
        "schema_version": "sim-learnability-probe-v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository_fingerprint(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "stable_baselines3": stable_baselines3.__version__,
            "torch": torch.__version__,
            "device": "cpu",
        },
        "protocol": {
            "train_seeds": TRAIN_SEEDS,
            "eval_seeds": EVAL_SEEDS,
            "train_eval_seed_overlap": False,
            "timesteps_per_algorithm_seed": TOTAL_TIMESTEPS,
            "max_train_seconds_per_run": MAX_TRAIN_SECONDS,
            "max_eval_episode_steps": MAX_EVAL_EPISODE_STEPS,
            "collapse_threshold": 0.98,
            "minimum_direction_share": MIN_DIRECTION_SHARE,
            "minimum_floor_advantage_over_random": MIN_FLOOR_ADVANTAGE,
        },
        "training": training,
        "baselines": {
            name: result.to_dict() for name, result in baselines.items()
        },
        "evaluations": {
            name: [result.to_dict() for result in results]
            for name, results in evaluations.items()
        },
        "per_seed_gates": per_seed_gates,
        "algorithm_gates": algorithm_gates,
        "gates": gates,
        "probe_pass": all(gates.values()),
        "next_action": (
            "Stop local budget expansion; validate Colab runtime."
            if all(gates.values())
            else "Stop budget expansion; diagnose failed seeds and reward."
        ),
    }
    report_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Simulator Learnability Probe P1 v1",
        "",
        f"- probe pass: **{payload['probe_pass']}**",
        f"- train seeds: {TRAIN_SEEDS}",
        f"- timesteps per algorithm/seed: {TOTAL_TIMESTEPS}",
        f"- held-out eval seeds: {len(EVAL_SEEDS)}",
        "",
        "## Baselines",
        "",
        "| Candidate | Floors | Return | Collapse |",
        "|---|---:|---:|---:|",
    ]
    for name, result in baselines.items():
        lines.append(
            f"| {name} | {result.mean_floors:.3f} | "
            f"{result.mean_return:.3f} | {result.collapsed} |"
        )
    lines += [
        "",
        "## Learners",
        "",
        "| Algorithm | Train seed | Floors | Return | Max share | Collapse |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for algorithm, results in evaluations.items():
        for train_seed, result in zip(TRAIN_SEEDS, results):
            lines.append(
                f"| {algorithm} | {train_seed} | "
                f"{result.mean_floors:.3f} | {result.mean_return:.3f} | "
                f"{result.max_action_share:.3f} | {result.collapsed} |"
            )
    lines += ["", "## Gates", ""]
    lines += [
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in gates.items()
    ]
    for algorithm, gate in algorithm_gates.items():
        lines.append(
            f"- {algorithm}: pass={gate['algorithm_pass']}, "
            f"mean floors={gate['mean_floors']:.3f}, "
            f"mean return={gate['mean_return']:.3f}"
        )
    lines += [
        "",
        f"Next: {payload['next_action']}",
        "",
        "SB3-DQN is explicitly not Double DQN.",
        "",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")
    for name, result in baselines.items():
        print(
            f"{name}: floors={result.mean_floors:.3f} "
            f"return={result.mean_return:.3f}"
        )
    for algorithm, results in evaluations.items():
        for train_seed, result in zip(TRAIN_SEEDS, results):
            print(
                f"{algorithm}/{train_seed}: floors={result.mean_floors:.3f} "
                f"return={result.mean_return:.3f} "
                f"max_share={result.max_action_share:.3f} "
                f"collapsed={result.collapsed}"
            )
    print(f"algorithm_gates={json.dumps(algorithm_gates)}")
    print(f"probe_pass={payload['probe_pass']}")
    print(f"report={report_md}")
    print(f"json={report_json}")


if __name__ == "__main__":
    run_main(main)
