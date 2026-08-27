"""Unified simulator-only PPO training CLI for V3 and R4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from stair_agent.training import TARGET_IDS, TrainingRequest, run_training
from stair_agent.training.trainer import FULL_TRAINING_AUTHORIZATION


ROOT = Path(__file__).resolve().parents[1]
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--target", choices=TARGET_IDS)
    selection.add_argument("--config", type=Path)
    parser.add_argument(
        "--mode", choices=("precheck", "smoke", "full"), default="precheck"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "runs")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--device")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--resume-metadata", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--authorization", default="")
    return parser.parse_args()


def _target_from_config(path: Path) -> str:
    resolved = path.resolve()
    allowed = {
        (ROOT / "configs/training/v3.yaml").resolve(): "v3",
        (ROOT / "configs/training/v3_5_r4.yaml").resolve(): "r4",
    }
    if resolved not in allowed:
        raise SystemExit("ONLY_CANONICAL_TRAINING_CONFIGS_ARE_ALLOWED")
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if raw.get("target") != allowed[resolved]:
        raise SystemExit("TRAINING_CONFIG_TARGET_MISMATCH")
    return allowed[resolved]


def main() -> int:
    args = parse_args()
    target_id = args.target or _target_from_config(args.config)
    if args.mode == "full" and args.authorization != FULL_TRAINING_AUTHORIZATION:
        raise SystemExit(
            "FULL_TRAINING_NOT_AUTHORIZED; pass --authorization "
            f"{FULL_TRAINING_AUTHORIZATION}"
        )
    result = run_training(
        TrainingRequest(
            target_id=target_id,
            project_root=ROOT,
            output_root=args.output,
            mode=args.mode,
            seed=args.seed,
            device=args.device,
            resume=args.resume,
            resume_metadata=args.resume_metadata,
            allow_dirty=args.allow_dirty,
            authorization=args.authorization,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.mode == "precheck":
        print("STAIRKID_TRAINING_PRECHECK=PASS")
        print("TRAINING_PERFORMED=NO")
    elif args.mode == "smoke":
        print("TRAINING_PERFORMED=SMOKE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
