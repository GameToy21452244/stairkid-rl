"""Capture manual-only simulator calibration metrics and traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.simulator.calibration_review import (
    capture_calibration_profile,
    write_calibration_comparison,
)
from stair_agent.simulator.manual_test import calibration_profile_config
from stair_agent.simulator.state import ShaftEnvConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", choices=("before", "after"), required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts") / "manual_simulator_calibration",
    )
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_root / args.label
    metrics = capture_calibration_profile(
        output_dir=output_dir,
        label=args.label,
        config=calibration_profile_config(ShaftEnvConfig(), args.label),
    )
    result: dict[str, object] = {
        "status": "CAPTURED",
        "label": args.label,
        "output_dir": str(output_dir.resolve()),
        "simulator_version": metrics["simulator_version"],
        "fps_invariance": metrics["fps_invariance"]["passed"],
        "holdout_used": False,
        "game_input_used": False,
        "training_started": False,
    }
    if args.compare:
        comparison = write_calibration_comparison(
            before_path=args.output_root / "before" / "metrics.json",
            after_path=args.output_root / "after" / "metrics.json",
            output_dir=args.output_root / "comparison",
        )
        result["comparison"] = comparison
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
