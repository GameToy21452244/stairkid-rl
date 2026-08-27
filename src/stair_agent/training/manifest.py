"""Reproducible training run metadata and atomic serialization."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_state(project_root: Path) -> tuple[str, bool]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GIT_STATE_FAILED:{' '.join(args)}")
        return result.stdout.strip()

    return run("rev-parse", "HEAD"), bool(run("status", "--porcelain"))


def dependency_versions() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python_version": platform.python_version(),
        "torch_version": None,
        "stable_baselines3_version": None,
    }
    try:
        import torch

        result["torch_version"] = torch.__version__
    except ImportError:
        pass
    try:
        import stable_baselines3

        result["stable_baselines3_version"] = stable_baselines3.__version__
    except ImportError:
        pass
    return result


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def initial_manifest(
    *,
    run_id: str,
    target_id: str,
    git_commit: str,
    git_dirty: bool,
    device: str,
    seed: int,
    start_timesteps: int,
    target_timesteps: int,
    config_sha256: str,
    source_model: str | None,
    source_model_sha256: str | None,
    training_assets: list[Mapping[str, Any]],
    training_performed: str,
) -> dict[str, Any]:
    return {
        "schema_version": "stairkid-training-run-v1",
        "run_id": run_id,
        "training_target": target_id,
        "started_at": utc_now(),
        "completed_at": None,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        **dependency_versions(),
        "device": device,
        "seed": int(seed),
        "start_timesteps": int(start_timesteps),
        "target_timesteps": int(target_timesteps),
        "config_sha256": config_sha256,
        "source_model": source_model,
        "source_model_sha256": source_model_sha256,
        "training_assets": [dict(item) for item in training_assets],
        "output_checkpoint": None,
        "output_sha256": None,
        "observation_space": [268],
        "action_space": "Discrete(3)",
        "training_performed": training_performed,
    }
