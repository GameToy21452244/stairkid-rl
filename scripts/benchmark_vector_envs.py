from __future__ import annotations

import json
import multiprocessing
import time
from datetime import datetime, timezone

import numpy as np
from gymnasium.vector import AsyncVectorEnv, SyncVectorEnv

from _common import PROJECT_ROOT, run_main
from stair_agent.envs.shaft_env import ShaftEnv


def make_env() -> ShaftEnv:
    return ShaftEnv()


def benchmark(vector_type, count: int, vector_steps: int = 1000) -> float:
    env = vector_type([make_env for _ in range(count)])
    try:
        env.reset(seed=list(range(count)))
        actions = np.zeros(count, dtype=np.int64)
        started = time.perf_counter()
        for _ in range(vector_steps):
            env.step(actions)
        elapsed = time.perf_counter() - started
        return count * vector_steps / elapsed
    finally:
        env.close()


def main() -> None:
    output = PROJECT_ROOT / "reports" / "VECTOR_ENV_BENCHMARK_V0.json"
    if output.exists():
        raise FileExistsError(f"拒絕覆寫 benchmark：{output}")
    rows = []
    for count in (1, 4, 8, 16):
        for mode, vector_type in (
            ("sync", SyncVectorEnv),
            ("async", AsyncVectorEnv),
        ):
            rate = benchmark(vector_type, count)
            rows.append(
                {"mode": mode, "env_count": count, "steps_per_second": rate}
            )
            print(f"{mode} envs={count}: {rate:.0f} steps/s")
    recommended = max(rows, key=lambda row: row["steps_per_second"])
    output.write_text(
        json.dumps(
            {
                "schema_version": "vector-env-benchmark-v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "vector_steps": 1000,
                "results": rows,
                "throughput_recommendation": recommended,
                "note": "Colab 必須重新 benchmark；本機結果不可直接外推。",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"recommendation={recommended}")
    print(f"artifact={output}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_main(main)
