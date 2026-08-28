"""CLI child for supervised, guarded Real bulk evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from stair_agent.core.model_registry import MODEL_IDS
from stair_agent.real.bulk import BulkEvaluationConfig, VIDEO_MODES, run_bulk_session


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bounded Real inference/evaluation; never training."
    )
    parser.add_argument("--model", choices=MODEL_IDS, required=True)
    parser.add_argument("--mode", choices=("shadow", "control"), required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--failure-diagnostics", action="store_true")
    parser.add_argument("--video-mode", choices=VIDEO_MODES, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/real_bulk"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--max-episode-seconds", type=float, default=180.0)
    parser.add_argument("--max-episode-steps", type=int, default=3600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = ROOT / output
    config = BulkEvaluationConfig(
        episodes=args.episodes,
        mode=args.mode,
        video_mode=args.video_mode,
        failure_diagnostics=args.failure_diagnostics,
        max_episode_seconds=args.max_episode_seconds,
        max_episode_steps=args.max_episode_steps,
    )
    result = run_bulk_session(
        ROOT,
        model_id=args.model,
        bulk_config=config,
        output_root=output,
        config_path=args.config,
    )
    print(f"REAL_BULK_SESSION_DIR={result['session_dir']}")
    print(f"REAL_BULK_SESSION_ZIP={result['archive']}")
    print(f"EPISODES_COMPLETED={result['summary']['episodes_completed']}")
    print(f"MEAN_FLOOR={result['summary']['mean_floor']}")
    print("TRAINING_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
