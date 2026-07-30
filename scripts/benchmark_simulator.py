from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from _common import PROJECT_ROOT, run_main
from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.envs.shaft_env import ShaftEnv, ShaftEnvConfig


def evaluate(name: str, seeds: list[int], episodes_per_seed: int) -> dict:
    episode_rows = []
    action_counts: Counter[int] = Counter()
    total_landings = 0
    for seed in seeds:
        rng = np.random.default_rng(seed + 50_000)
        for episode in range(episodes_per_seed):
            env = ShaftEnv(config=ShaftEnvConfig(max_episode_steps=500))
            policy = SafePlatformPolicy(BaselineConfig())
            _obs, _info = env.reset(seed=seed * 1000 + episode)
            total_reward = 0.0
            floors = 0
            reason = None
            try:
                for length in range(1, 501):
                    if name == "random":
                        action = int(rng.integers(0, 3))
                    elif name == "release":
                        action = 0
                    else:
                        action = int(policy.choose(env.last_observation).action)
                    action_counts[action] += 1
                    _obs, reward, terminated, truncated, info = env.step(action)
                    total_reward += reward
                    total_landings += int("landed" in info["events"])
                    floors += int("floor_descended" in info["events"])
                    if terminated or truncated:
                        reason = info["terminal_reason"]
                        break
                episode_rows.append(
                    {
                        "seed": seed,
                        "episode": episode,
                        "length": length,
                        "return": total_reward,
                        "floors": floors,
                        "terminal_reason": reason,
                    }
                )
            finally:
                env.close()
    total_steps = sum(row["length"] for row in episode_rows)
    total_floors = sum(row["floors"] for row in episode_rows)
    return {
        "episodes": len(episode_rows),
        "mean_floors": float(np.mean([row["floors"] for row in episode_rows])),
        "median_floors": float(np.median([row["floors"] for row in episode_rows])),
        "mean_length": float(np.mean([row["length"] for row in episode_rows])),
        "mean_return": float(np.mean([row["return"] for row in episode_rows])),
        "total_steps": total_steps,
        "total_landings": total_landings,
        "total_floors": total_floors,
        "landing_rate_per_step": total_landings / total_steps,
        "floor_rate_per_step": total_floors / total_steps,
        "action_counts": {str(k): v for k, v in sorted(action_counts.items())},
        "terminal_reasons": dict(
            Counter(str(row["terminal_reason"]) for row in episode_rows)
        ),
        "episode_results": episode_rows,
    }


def main() -> None:
    output = (
        PROJECT_ROOT
        / "reports"
        / "SIMULATOR_BENCHMARK_V0_1_FIDELITY.json"
    )
    if output.exists():
        raise FileExistsError(f"拒絕覆寫 benchmark：{output}")
    seeds = [1001, 1002, 1003, 1004, 1005]
    results = {
        name: evaluate(name, seeds, 20)
        for name in ("random", "release", "baseline")
    }
    payload = {
        "schema_version": "simulator-benchmark-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulator": "v0.1-calibrated",
        "seeds": seeds,
        "episodes_per_seed": 20,
        "max_episode_steps": 500,
        "results": results,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for name, result in results.items():
        print(
            f"{name}: floors={result['mean_floors']:.3f} "
            f"length={result['mean_length']:.1f} "
            f"return={result['mean_return']:.3f} "
            f"landing_rate={result['landing_rate_per_step']:.4f} "
            f"floor_rate={result['floor_rate_per_step']:.4f}"
        )
    print(f"artifact={output}")


if __name__ == "__main__":
    run_main(main)
