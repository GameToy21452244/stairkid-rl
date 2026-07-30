from __future__ import annotations

import argparse
import time

from _common import run_main

from gymnasium.utils.env_checker import check_env

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.config import BaselineConfig
from stair_agent.envs.shaft_env import ShaftEnv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="離線檢查模擬器；不尋找遊戲、不送鍵盤輸入。"
    )
    parser.add_argument("--steps", type=int, default=10_000)
    parser.add_argument("--baseline-steps", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.steps < 1 or args.baseline_steps < 1:
        raise ValueError("步數必須大於 0。")
    env = ShaftEnv()
    started = time.perf_counter()
    try:
        check_env(env, skip_render_check=True)
        env.reset(seed=args.seed)
        for _ in range(args.steps):
            _obs, _reward, terminated, truncated, _info = env.step(
                env.action_space.sample()
            )
            if terminated or truncated:
                env.reset()
        elapsed = time.perf_counter() - started

        policy = SafePlatformPolicy(BaselineConfig())
        env.reset(seed=args.seed)
        for _ in range(args.baseline_steps):
            decision = policy.choose(env.last_observation)
            _obs, _reward, terminated, truncated, _info = env.step(
                int(decision.action)
            )
            if terminated or truncated:
                env.reset()
                policy.reset()
    finally:
        env.close()
    print("Gymnasium check_env：通過")
    print(
        f"headless smoke：{args.steps} steps / {elapsed:.3f}s "
        f"({args.steps / elapsed:.0f} steps/s)"
    )
    print(f"baseline smoke：{args.baseline_steps} steps 通過")
    print("全程未載入真實遊戲輸入後端。")


if __name__ == "__main__":
    run_main(main)
