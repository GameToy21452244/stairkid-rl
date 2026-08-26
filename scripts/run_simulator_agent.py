"""Run an explicitly selected canonical PPO policy in the corrected simulator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stair_agent.sim.runtime import run_simulator_policy


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=("v3", "r4"))
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=3600)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Disable the Pygame window; intended for automated smoke checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_simulator_policy(
        ROOT,
        args.model,
        episodes=args.episodes,
        max_steps_per_episode=args.max_steps,
        base_seed=args.seed,
        render_mode=None if args.headless else "human",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
