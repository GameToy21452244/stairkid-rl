"""Generic deterministic evaluation in the corrected local simulator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stair_agent.evaluation import floor_metrics, write_json_report
from stair_agent.sim.runtime import run_simulator_policy


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one exact canonical policy in the local simulator."
    )
    parser.add_argument("--model", required=True, choices=("v3", "r4"))
    parser.add_argument("--episodes", type=int, default=64)
    parser.add_argument("--max-steps", type=int, default=3600)
    parser.add_argument("--seed", type=int, default=50_000_000)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.episodes <= 1000:
        raise SystemExit("--episodes must be between 1 and 1000")
    if not 1 <= args.max_steps <= 100_000:
        raise SystemExit("--max-steps must be between 1 and 100000")
    result = run_simulator_policy(
        ROOT,
        args.model,
        episodes=args.episodes,
        max_steps_per_episode=args.max_steps,
        base_seed=args.seed,
        render_mode=None,
    )
    result["floor_metrics"] = floor_metrics(
        episode["deepest_floor"] for episode in result["episodes"]
    )
    if args.output is not None:
        write_json_report(args.output, result)
        result["report_path"] = str(args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("SIMULATOR_EVALUATION=PASS")
    print("REAL_GAME_EXECUTED=NO")
    print("TRAINING_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
