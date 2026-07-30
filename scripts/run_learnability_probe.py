from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from _common import PROJECT_ROOT, run_main
from stair_agent.envs.shaft_env import ShaftEnv, ShaftEnvConfig
from stair_agent.learnability import (
    baseline_selector,
    evaluate_candidate,
    learned_selector,
    random_selector,
    release_selector,
)
from stair_agent.rl_training import SafetyStopCallback


EXPERIMENT_ID = "sim_learnability_p0_v1"
TRAIN_SEED = 31_001
EVAL_SEEDS = list(range(41_001, 41_021))
TOTAL_TIMESTEPS = 4_096
MAX_TRAIN_SECONDS = 60.0
MAX_EVAL_EPISODE_STEPS = 120


def repository_fingerprint() -> dict[str, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return {
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def make_env(max_steps: int = MAX_EVAL_EPISODE_STEPS) -> ShaftEnv:
    return ShaftEnv(config=ShaftEnvConfig(max_episode_steps=max_steps))


def train_ppo(
    output: Path,
    *,
    train_seed: int = TRAIN_SEED,
    total_timesteps: int = TOTAL_TIMESTEPS,
    max_train_seconds: float = MAX_TRAIN_SECONDS,
):
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env

    env = make_vec_env(
        make_env,
        n_envs=4,
        seed=train_seed,
    )
    callback = SafetyStopCallback(max_seconds=max_train_seconds)
    started = time.monotonic()
    try:
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=128,
            batch_size=64,
            n_epochs=4,
            gamma=0.99,
            gae_lambda=0.95,
            ent_coef=0.01,
            policy_kwargs={"net_arch": [64, 64]},
            seed=train_seed,
            device="cpu",
            verbose=0,
        )
        model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            progress_bar=False,
        )
        model.save(output)
        return model, {
            "algorithm": "PPO",
            "requested_timesteps": total_timesteps,
            "actual_timesteps": int(model.num_timesteps),
            "elapsed_seconds": time.monotonic() - started,
            "stop_reason": callback.stop_reason or "timestep_limit",
        }
    finally:
        env.close()


def train_dqn(
    output: Path,
    *,
    train_seed: int = TRAIN_SEED,
    total_timesteps: int = TOTAL_TIMESTEPS,
    max_train_seconds: float = MAX_TRAIN_SECONDS,
):
    from stable_baselines3 import DQN

    env = make_env()
    env.reset(seed=train_seed)
    callback = SafetyStopCallback(max_seconds=max_train_seconds)
    started = time.monotonic()
    try:
        model = DQN(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            buffer_size=5_000,
            learning_starts=256,
            batch_size=64,
            tau=1.0,
            gamma=0.99,
            train_freq=4,
            gradient_steps=1,
            target_update_interval=250,
            exploration_fraction=0.5,
            exploration_final_eps=0.05,
            policy_kwargs={"net_arch": [64, 64]},
            seed=train_seed,
            device="cpu",
            verbose=0,
        )
        model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            progress_bar=False,
        )
        model.save(output)
        return model, {
            "algorithm": "SB3-DQN",
            "double_dqn": False,
            "requested_timesteps": total_timesteps,
            "actual_timesteps": int(model.num_timesteps),
            "elapsed_seconds": time.monotonic() - started,
            "stop_reason": callback.stop_reason or "timestep_limit",
        }
    finally:
        env.close()


def main() -> None:
    import stable_baselines3
    import torch

    model_dir = PROJECT_ROOT / "models" / "probes" / EXPERIMENT_ID
    report_json = (
        PROJECT_ROOT / "reports" / "SIM_LEARNABILITY_PROBE_P0_V1.json"
    )
    report_md = (
        PROJECT_ROOT / "reports" / "SIM_LEARNABILITY_PROBE_P0_V1.md"
    )
    for path in (model_dir, report_json, report_md):
        if path.exists():
            raise FileExistsError(f"拒絕覆寫既有 probe artifact：{path}")
    model_dir.mkdir(parents=True)

    evaluations = {
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
    ppo_model, ppo_training = train_ppo(model_dir / "ppo_model")
    dqn_model, dqn_training = train_dqn(model_dir / "dqn_model")
    evaluations["ppo"] = evaluate_candidate(
        "ppo",
        learned_selector(ppo_model),
        seeds=EVAL_SEEDS,
        max_episode_steps=MAX_EVAL_EPISODE_STEPS,
    )
    evaluations["sb3_dqn"] = evaluate_candidate(
        "sb3_dqn",
        learned_selector(dqn_model),
        seeds=EVAL_SEEDS,
        max_episode_steps=MAX_EVAL_EPISODE_STEPS,
    )

    random_result = evaluations["random"]
    baseline_result = evaluations["baseline"]
    learner_gates = {}
    for name in ("ppo", "sb3_dqn"):
        result = evaluations[name]
        learner_gates[name] = {
            "no_action_collapse": not result.collapsed,
            "mean_floors_ge_random": (
                result.mean_floors >= random_result.mean_floors
            ),
            "mean_return_ge_random": (
                result.mean_return >= random_result.mean_return
            ),
        }
        learner_gates[name]["candidate_pass"] = all(
            learner_gates[name].values()
        )
    gates = {
        "baseline_mean_floors_gt_random": (
            baseline_result.mean_floors > random_result.mean_floors
        ),
        "ppo_pipeline_complete": (
            ppo_training["actual_timesteps"] > 0
            and (model_dir / "ppo_model.zip").is_file()
        ),
        "dqn_pipeline_complete": (
            dqn_training["actual_timesteps"] > 0
            and (model_dir / "dqn_model.zip").is_file()
        ),
        "at_least_one_learner_pass": any(
            result["candidate_pass"] for result in learner_gates.values()
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
            "train_seed": TRAIN_SEED,
            "eval_seeds": EVAL_SEEDS,
            "train_eval_seed_overlap": False,
            "timesteps_per_algorithm": TOTAL_TIMESTEPS,
            "max_train_seconds_per_algorithm": MAX_TRAIN_SECONDS,
            "max_eval_episode_steps": MAX_EVAL_EPISODE_STEPS,
            "deterministic_evaluation": True,
            "collapse_threshold": 0.98,
        },
        "training": {
            "ppo": ppo_training,
            "sb3_dqn": dqn_training,
        },
        "evaluations": {
            name: result.to_dict() for name, result in evaluations.items()
        },
        "learner_gates": learner_gates,
        "gates": gates,
        "probe_pass": all(gates.values()),
        "next_action": (
            "Design bounded P1 multi-seed probe."
            if all(gates.values())
            else "Stop budget expansion; diagnose reward/observation/action collapse."
        ),
    }
    report_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Simulator Learnability Probe P0 v1",
        "",
        f"- probe pass: **{payload['probe_pass']}**",
        f"- train seed: {TRAIN_SEED}",
        f"- timesteps per algorithm: {TOTAL_TIMESTEPS}",
        f"- evaluation: {len(EVAL_SEEDS)} held-out seeds × "
        f"{MAX_EVAL_EPISODE_STEPS} max steps",
        "",
        "## Results",
        "",
        "| Candidate | Floors | Return | Length | Max action share | Collapse |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, result in evaluations.items():
        lines.append(
            f"| {name} | {result.mean_floors:.3f} | "
            f"{result.mean_return:.3f} | {result.mean_length:.1f} | "
            f"{result.max_action_share:.3f} | {result.collapsed} |"
        )
    lines += ["", "## Gates", ""]
    lines += [
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in gates.items()
    ]
    lines += [
        "",
        f"Next: {payload['next_action']}",
        "",
        "SB3-DQN is explicitly not Double DQN.",
        "",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["training"], ensure_ascii=False, indent=2))
    for name, result in evaluations.items():
        print(
            f"{name}: floors={result.mean_floors:.3f} "
            f"return={result.mean_return:.3f} "
            f"max_action_share={result.max_action_share:.3f} "
            f"collapsed={result.collapsed}"
        )
    print(f"probe_pass={payload['probe_pass']}")
    print(f"report={report_md}")
    print(f"json={report_json}")


if __name__ == "__main__":
    run_main(main)
