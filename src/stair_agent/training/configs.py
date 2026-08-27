"""Fail-closed parser for the two retained training presets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


TARGET_IDS = ("v3", "r4")
TARGET_CONFIGS = {
    "v3": Path("configs/training/v3.yaml"),
    "r4": Path("configs/training/v3_5_r4.yaml"),
}


class TrainingConfigError(RuntimeError):
    pass


def canonical_config_bytes(raw: Mapping[str, Any]) -> bytes:
    return json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class TrainingTarget:
    id: str
    path: Path
    raw: Mapping[str, Any]
    config_sha256: str

    @property
    def algorithm(self) -> Mapping[str, Any]:
        return self.raw["algorithm"]

    @property
    def environment(self) -> Mapping[str, Any]:
        return self.raw["environment"]

    @property
    def training(self) -> Mapping[str, Any]:
        return self.raw["training"]

    @property
    def default_seed(self) -> int:
        return int(self.algorithm["default_seed"])

    @property
    def total_timesteps(self) -> int:
        return int(self.training["total_timesteps"])

    @property
    def observation_shape(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self.environment["observation_shape"])

    @property
    def action_count(self) -> int:
        return int(self.environment["action_count"])


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TrainingConfigError(f"TRAINING_CONFIG_{name}_MUST_BE_MAPPING")
    return value


def _validate(raw: Mapping[str, Any], target_id: str) -> None:
    required_sections = {
        "schema_version",
        "target",
        "display_name",
        "status",
        "provenance",
        "algorithm",
        "environment",
        "training",
        "curriculum",
        "evaluation",
        "assets",
        "resume",
        "safety",
    }
    missing = sorted(required_sections - set(raw))
    if missing:
        raise TrainingConfigError(f"TRAINING_CONFIG_FIELDS_MISSING:{missing}")
    if raw["schema_version"] != "stairkid-unified-training-v1":
        raise TrainingConfigError("TRAINING_CONFIG_SCHEMA_INVALID")
    if raw["target"] != target_id or target_id not in TARGET_IDS:
        raise TrainingConfigError("TRAINING_TARGET_INVALID")
    provenance = _mapping(raw["provenance"], "PROVENANCE")
    unresolved = provenance.get("unresolved_fields")
    if not isinstance(unresolved, list):
        raise TrainingConfigError("TRAINING_UNRESOLVED_PROVENANCE_INVALID")
    algorithm = _mapping(raw["algorithm"], "ALGORITHM")
    expected_ppo = {
        "name": "PPO",
        "policy": "MlpPolicy",
        "n_envs": 4,
        "n_steps": 1024,
        "batch_size": 256,
        "n_epochs": 10,
        "learning_rate": 0.0003,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "clip_range": 0.2,
        "ent_coef": 0.01,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
    }
    for name, expected in expected_ppo.items():
        if algorithm.get(name) != expected:
            raise TrainingConfigError(f"TRAINING_PPO_CONTRACT_MISMATCH:{name}")
    seeds = tuple(int(value) for value in algorithm.get("seed_candidates", []))
    expected_seeds = (17, 42, 83) if target_id == "v3" else (117, 142)
    if seeds != expected_seeds or int(algorithm.get("default_seed", -1)) not in seeds:
        raise TrainingConfigError("TRAINING_SEED_CONTRACT_INVALID")
    environment = _mapping(raw["environment"], "ENVIRONMENT")
    if tuple(environment.get("observation_shape", [])) != (268,):
        raise TrainingConfigError("TRAINING_OBSERVATION_CONTRACT_INVALID")
    if int(environment.get("action_count", -1)) != 3:
        raise TrainingConfigError("TRAINING_ACTION_CONTRACT_INVALID")
    if int(environment.get("physics_hz", -1)) != 60:
        raise TrainingConfigError("TRAINING_PHYSICS_CONTRACT_INVALID")
    training = _mapping(raw["training"], "TRAINING")
    targets = tuple(int(value) for value in training.get("checkpoint_targets", []))
    expected_targets = (
        (98_304, 196_608, 294_912, 393_216, 524_288, 655_360)
        if target_id == "v3"
        else (589_824, 655_360, 720_896)
    )
    if targets != expected_targets or int(training.get("total_timesteps", -1)) != expected_targets[-1]:
        raise TrainingConfigError("TRAINING_TIMESTEP_CONTRACT_INVALID")
    if int(training.get("rollout_quantum", -1)) != 4096:
        raise TrainingConfigError("TRAINING_ROLLOUT_QUANTUM_INVALID")
    safety = _mapping(raw["safety"], "SAFETY")
    if safety.get("canonical_models_read_only") is not True:
        raise TrainingConfigError("CANONICAL_MODEL_WRITE_GUARD_REQUIRED")
    if safety.get("real_game_execution") != "FORBIDDEN":
        raise TrainingConfigError("TRAINING_REAL_GAME_MUST_BE_FORBIDDEN")
    if target_id == "r4":
        reward = _mapping(raw.get("reward"), "REWARD")
        if float(reward.get("edge_landing_penalty", -1)) != 1.10:
            raise TrainingConfigError("R4_EDGE_LANDING_PENALTY_MUST_BE_1_10")
        curriculum = _mapping(raw["curriculum"], "CURRICULUM")
        if curriculum.get("r1_retraining_forbidden") is not True:
            raise TrainingConfigError("R4_R1_RETRAINING_MUST_BE_FORBIDDEN")
        if curriculum.get("bank_recollection_forbidden") is not True:
            raise TrainingConfigError("R4_BANK_RECOLLECTION_MUST_BE_FORBIDDEN")


def load_training_target(project_root: Path, target_id: str) -> TrainingTarget:
    if target_id not in TARGET_CONFIGS:
        raise TrainingConfigError(f"UNKNOWN_TRAINING_TARGET:{target_id}")
    path = (project_root.resolve() / TARGET_CONFIGS[target_id]).resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TrainingConfigError(f"TRAINING_CONFIG_READ_FAILED:{path}") from exc
    raw = _mapping(raw, "ROOT")
    _validate(raw, target_id)
    digest = hashlib.sha256(canonical_config_bytes(raw)).hexdigest()
    return TrainingTarget(target_id, path, raw, digest)


def load_training_registry(project_root: Path) -> dict[str, TrainingTarget]:
    return {target_id: load_training_target(project_root, target_id) for target_id in TARGET_IDS}
