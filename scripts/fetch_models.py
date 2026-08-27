"""Fetch exact canonical model assets into the ignored local cache."""

from __future__ import annotations

import argparse
from pathlib import Path

from stair_agent.training.model_fetch import fetch_model


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model", choices=("v3", "r4"))
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    model_ids = ("v3", "r4") if args.all else (args.model,)
    for model_id in model_ids:
        path = fetch_model(ROOT, str(model_id), source_dir=args.source_dir)
        print(f"MODEL_{str(model_id).upper()}={path}")
    print("MODEL_FETCH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
