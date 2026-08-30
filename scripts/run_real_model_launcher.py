"""Interactive, input-free launcher for the guarded Real bulk child runner."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

from stair_agent.core.model_registry import load_model_registry, sha256_file
from stair_agent.real.setup import inspect_real_setup


ROOT = Path(__file__).resolve().parents[1]
MODEL_MENU = {"1": "v3", "2": "r4"}
MODE_MENU = {"1": "shadow", "2": "control"}
VIDEO_MENU = {"1": "none", "2": "best", "3": "all"}


@dataclass(frozen=True)
class LaunchPlan:
    model_id: str
    mode: str
    episodes: int
    failure_diagnostics: bool
    video_mode: str
    output_dir: Path


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def parse_episode_count(value: str) -> int:
    try:
        episodes = int(value.strip())
    except ValueError as exc:
        raise ValueError("EPISODES_MUST_BE_INTEGER") from exc
    if not 1 <= episodes <= 100:
        raise ValueError("EPISODES_OUT_OF_RANGE: expected 1..100")
    return episodes


def _yes_no(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"y", "yes"}:
        return True
    if normalized in {"n", "no"}:
        return False
    raise ValueError("EXPECTED_YES_OR_NO")


def verify_model_archive(root: Path, model_id: str) -> None:
    registry = load_model_registry(root)
    if model_id not in registry:
        raise RuntimeError(f"UNKNOWN_MODEL_ID:{model_id}")
    model = registry[model_id]
    if not model.asset_path.is_file():
        raise RuntimeError(f"CANONICAL_MODEL_FILE_REQUIRED:{model_id}:{model.asset_path}")
    digest = sha256_file(model.asset_path)
    if digest != model.sha256:
        raise RuntimeError(f"MODEL_SHA_MISMATCH:{model_id}:{digest}!={model.sha256}")


def build_child_command(root: Path, python_executable: Path, plan: LaunchPlan) -> list[str]:
    command = [
        str(python_executable),
        str(root / "scripts/bulk_real_evaluation.py"),
        "--model",
        plan.model_id,
        "--mode",
        plan.mode,
        "--episodes",
        str(plan.episodes),
        "--video-mode",
        plan.video_mode,
        "--output-dir",
        str(plan.output_dir),
    ]
    if plan.failure_diagnostics:
        command.append("--failure-diagnostics")
    return command


def interactive_main(
    *,
    project_root: Path = ROOT,
    python_executable: Path = Path(sys.executable),
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    run_fn: Callable[..., object] = subprocess.run,
) -> int:
    root = project_root.resolve()
    setup = inspect_real_setup(root)
    if not setup.ready:
        output_fn("REAL_SETUP_REQUIRED")
        output_fn(f"REAL_CONFIG={setup.config_path}")
        for problem in setup.problems:
            output_fn(f"REAL_SETUP_PROBLEM={problem}")
        for path in setup.missing_templates:
            output_fn(f"MISSING_REAL_TEMPLATE={path}")
        output_fn("Run FIRST_RUN_SETUP.cmd and CALIBRATE_REAL_GAME.cmd first.")
        return 5
    registry = load_model_registry(root)
    output_fn("=" * 64)
    output_fn("StairKid RL - Guarded Real Model Test")
    output_fn("F8 = emergency stop. This is inference/evaluation, never training.")
    output_fn("=" * 64)
    for choice, model_id in MODEL_MENU.items():
        model = registry[model_id]
        output_fn(
            f"{choice} = {model.display_name} | ID={model.id} | "
            f"SHA256={model.sha256} | STATUS={model.status}"
        )
    model_choice = input_fn("MODEL [1/2]: ").strip()
    if model_choice not in MODEL_MENU:
        output_fn("INVALID_MODEL_SELECTION")
        return 2
    model_id = MODEL_MENU[model_choice]
    output_fn("1 = Shadow (capture/inference only; zero actions)")
    output_fn("2 = Control (requires a second Python authorization)")
    mode_choice = input_fn("MODE [1/2]: ").strip()
    if mode_choice not in MODE_MENU:
        output_fn("INVALID_MODE_SELECTION")
        return 2
    try:
        episodes = parse_episode_count(input_fn("EPISODES [1-100]: "))
        diagnostics = _yes_no(input_fn("FAILURE DIAGNOSTICS [YES/NO]: "))
    except ValueError as exc:
        output_fn(str(exc))
        return 2
    output_fn("1 = none, 2 = best, 3 = all")
    video_choice = input_fn("VIDEO MODE [1/2/3]: ").strip()
    if video_choice not in VIDEO_MENU:
        output_fn("INVALID_VIDEO_MODE")
        return 2
    plan = LaunchPlan(
        model_id=model_id,
        mode=MODE_MENU[mode_choice],
        episodes=episodes,
        failure_diagnostics=diagnostics,
        video_mode=VIDEO_MENU[video_choice],
        output_dir=root / "runs/real_bulk",
    )
    try:
        verify_model_archive(root, model_id)
        branch = _git(root, "branch", "--show-current")
        commit = _git(root, "rev-parse", "HEAD")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        output_fn(f"PREFLIGHT_MODEL_OR_GIT_FAILURE:{exc}")
        return 3
    model = registry[model_id]
    child = root / "scripts/bulk_real_evaluation.py"
    output_fn("\nRUN SUMMARY")
    for key, value in (
        ("PROJECT_ROOT", root),
        ("GIT_BRANCH", branch),
        ("GIT_COMMIT", commit),
        ("MODEL_ID", model.id),
        ("MODEL_SHA256", model.sha256),
        ("MODEL_STATUS", model.status),
        ("MODE", plan.mode.upper()),
        ("EPISODES", plan.episodes),
        ("FAILURE_DIAGNOSTICS", "YES" if diagnostics else "NO"),
        ("VIDEO_MODE", plan.video_mode),
        ("OUTPUT_DIR", plan.output_dir),
        ("CHILD_RUNNER", child),
    ):
        output_fn(f"{key}={value}")
    if input_fn("Type exact RUN to continue: ").strip() != "RUN":
        output_fn("RUN_GATE_REJECTED; no Real session started.")
        return 2
    command = build_child_command(root, python_executable, plan)
    completed = run_fn(command, cwd=root, check=False)
    return int(getattr(completed, "returncode", 0))


if __name__ == "__main__":
    raise SystemExit(interactive_main())
