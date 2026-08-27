"""Fetch SHA-pinned external training assets; repository source is never fetched."""

from __future__ import annotations

import argparse
from pathlib import Path

from stair_agent.training.assets import fetch_training_assets


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, choices=("v3", "r4"))
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    paths = fetch_training_assets(ROOT, args.target, source_dir=args.source_dir)
    for path in paths:
        print(f"TRAINING_ASSET={path}")
    print("TRAINING_ASSET_FETCH=PASS")
    print("PROJECT_SOURCE_FETCHED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
