"""Canonical Real PPO entry point for retained V3 and R4 policies."""

from __future__ import annotations

import argparse
from pathlib import Path

from stair_agent.core.model_registry import load_canonical_model
from stair_agent.real.runtime import prepare_real_dry_run, run_live_real


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a canonical PPO model and Real observation pipeline."
    )
    parser.add_argument("--model", required=True, choices=("v3", "r4"))
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; never construct capture/controller or send input.",
    )
    parser.add_argument(
        "--control",
        action="store_true",
        help="Send policy actions after an exact interactive authorization phrase.",
    )
    parser.add_argument("--max-steps", type=int, default=1800)
    parser.add_argument("--max-seconds", type=float, default=180.0)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run and args.control:
        raise SystemExit("--dry-run and --control are mutually exclusive")
    if args.dry_run:
        result = prepare_real_dry_run(
            PROJECT_ROOT,
            args.model,
            config_path=args.config,
            device=args.device,
        )
        loaded = result.loaded_model
    else:
        loaded = load_canonical_model(PROJECT_ROOT, args.model, device=args.device)
    spec = loaded.spec
    print(f"MODEL_ID={spec.id}")
    print(f"DISPLAY_NAME={spec.display_name}")
    print(f"MODEL_PATH={loaded.path}")
    print(f"MODEL_SHA256={spec.sha256}")
    print(f"SEED={spec.seed}")
    print(f"NUM_TIMESTEPS={spec.timesteps}")
    print(f"STATUS={spec.status}")
    print(f"OBSERVATION_SPACE={loaded.model.observation_space}")
    print(f"ACTION_SPACE={loaded.model.action_space}")
    if args.dry_run:
        print(f"CONFIG={result.config_path}")
        print(f"CAPTURE_CONSTRUCTED={result.capture_constructed}")
        print(f"CONTROLLER_CONSTRUCTED={result.controller_constructed}")
        print(f"ACTIONS_SENT={result.actions_sent}")
        print("REAL_DRY_RUN=PASS")
        return 0

    if args.control:
        phrase = f"AUTHORIZE_{spec.id.upper()}_REAL_CONTROL"
        print("CONTROL_MODE=REQUESTED")
        print("F8=EMERGENCY_STOP")
        if input(f"Type {phrase} to continue: ").strip() != phrase:
            raise SystemExit("REAL_CONTROL_NOT_AUTHORIZED")
    else:
        print("MODE=SHADOW")
        print("ACTIONS_WILL_BE_SENT=NO")

    live_result = run_live_real(
        PROJECT_ROOT,
        loaded,
        config_path=args.config,
        control=args.control,
        max_steps=args.max_steps,
        max_seconds=args.max_seconds,
    )
    print(f"MODE={live_result.mode}")
    print(f"STEPS={live_result.steps}")
    print(f"ACTIONS_SENT={live_result.actions_sent}")
    print(f"TERMINAL_REASON={live_result.terminal_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
