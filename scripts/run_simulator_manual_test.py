"""Run the local-keyboard, simulator-only manual test viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.simulator.manual_test import (
    DEFAULT_MANUAL_SEED,
    DEFAULT_OUTPUT_ROOT,
    ManualSimulatorSession,
    list_manual_scenarios,
    run_headless_smoke,
    run_manual_viewer,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=[item.name for item in list_manual_scenarios()],
        default="normal_baseline",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_MANUAL_SEED)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--show-debug", action="store_true")
    parser.add_argument(
        "--profile",
        choices=("before", "after"),
        default="after",
        help="切換v0.3修正前或v0.4 calibration candidate。",
    )
    parser.add_argument("--fps", type=int, default=60, help="視窗更新FPS；physics仍固定60Hz，control仍10Hz。")
    parser.add_argument("--headless-smoke", action="store_true")
    parser.add_argument("--smoke-steps", type=int, default=6)
    parser.add_argument("--list-scenarios", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_scenarios:
        for item in list_manual_scenarios():
            print(
                f"{item.scenario_id} {item.name}: {item.title} "
                f"[{item.validation_status}]"
            )
        return 0
    if args.headless_smoke:
        result = run_headless_smoke(
            output_root=args.output_dir,
            seed=args.seed,
            steps=args.smoke_steps,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    session = ManualSimulatorSession(
        scenario=args.scenario,
        seed=args.seed,
        output_root=args.output_dir,
        display_fps=args.fps,
        show_debug=args.show_debug,
        record_video=args.record,
        calibration_profile=args.profile,
    )
    try:
        run_manual_viewer(session)
    except KeyboardInterrupt:
        print("Manual simulator收到Ctrl+C，安全保存目前紀錄。")
    finally:
        output_dir = session.close()
    print(f"Manual simulator紀錄：{output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
