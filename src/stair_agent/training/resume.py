"""Resume validation with target/config binding and remaining-step semantics."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from stair_agent.core.model_registry import sha256_file
from .configs import TrainingTarget


class ResumeValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ValidatedResume:
    path: Path
    sha256: str
    model: Any
    current_timesteps: int
    target_timesteps: int
    remaining_timesteps: int


def validate_resume(
    checkpoint: Path,
    target: TrainingTarget,
    *,
    env: Any,
    expected_sha256: str | None = None,
    metadata_path: Path | None = None,
    device: str = "cpu",
    allow_pinned_external: bool = False,
) -> ValidatedResume:
    path = checkpoint.resolve()
    if not path.is_file():
        raise ResumeValidationError(f"RESUME_CHECKPOINT_REQUIRED:{path}")
    actual_sha = sha256_file(path)
    if expected_sha256 is not None and actual_sha != expected_sha256:
        raise ResumeValidationError("RESUME_CHECKPOINT_SHA_MISMATCH")
    if metadata_path is not None:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResumeValidationError("RESUME_METADATA_INVALID") from exc
        if metadata.get("training_target") != target.id:
            raise ResumeValidationError("RESUME_TARGET_MISMATCH")
        if metadata.get("config_sha256") != target.config_sha256:
            raise ResumeValidationError("RESUME_CONFIG_MISMATCH")
        if metadata.get("output_sha256") not in {None, actual_sha}:
            raise ResumeValidationError("RESUME_METADATA_SHA_MISMATCH")
    elif target.raw["resume"]["require_matching_target_and_config_metadata"] and not allow_pinned_external:
        raise ResumeValidationError("RESUME_METADATA_REQUIRED")

    from stable_baselines3 import PPO

    try:
        model = PPO.load(path, env=env, device=device)
    except (ValueError, TypeError) as exc:
        raise ResumeValidationError("RESUME_MODEL_ENVIRONMENT_INCOMPATIBLE") from exc
    if tuple(model.observation_space.shape) != target.observation_shape:
        raise ResumeValidationError("RESUME_OBSERVATION_SPACE_MISMATCH")
    if int(model.action_space.n) != target.action_count:
        raise ResumeValidationError("RESUME_ACTION_SPACE_MISMATCH")
    current = int(model.num_timesteps)
    allowed = tuple(int(value) for value in target.raw["resume"]["allowed_initial_timesteps"])
    if current not in allowed and not allow_pinned_external:
        raise ResumeValidationError(f"RESUME_TIMESTEPS_NOT_ALLOWED:{current}")
    if current >= target.total_timesteps:
        if current > target.total_timesteps or not allow_pinned_external:
            raise ResumeValidationError(
                f"RESUME_TARGET_NOT_AHEAD:{current}>={target.total_timesteps}"
            )
    remaining = max(0, target.total_timesteps - current)
    return ValidatedResume(path, actual_sha, model, current, target.total_timesteps, remaining)
