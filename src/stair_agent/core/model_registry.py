"""Fail-closed registry and loader for the two retained PPO policies."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

import numpy as np


MODEL_IDS = ("v3", "r4")
MANIFEST_RELATIVE_PATH = Path("models/manifest.json")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ModelRegistryError(RuntimeError):
    """A canonical model identity or compatibility check failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class CanonicalModel:
    id: str
    display_name: str
    seed: int
    timesteps: int
    sha256: str
    policy_parameter_sha256: str | None
    status: str
    description: str
    asset_path: Path
    asset_source: str
    observation_shape: tuple[int, ...]
    action_count: int
    simulator_profile: Path
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class LoadedCanonicalModel:
    spec: CanonicalModel
    path: Path
    model: Any
    policy_parameter_sha256: str | None

    def predict(self, observation: np.ndarray) -> int:
        array = np.asarray(observation, dtype=np.float32)
        if tuple(array.shape) != self.spec.observation_shape:
            raise ModelRegistryError(
                f"OBSERVATION_SHAPE_MISMATCH:{tuple(array.shape)}!={self.spec.observation_shape}"
            )
        if not np.isfinite(array).all():
            raise ModelRegistryError("OBSERVATION_NON_FINITE")
        action, _ = self.model.predict(array, deterministic=True)
        action_index = int(np.asarray(action).item())
        if not 0 <= action_index < self.spec.action_count:
            raise ModelRegistryError(f"MODEL_RETURNED_INVALID_ACTION:{action_index}")
        return action_index


def _project_path(project_root: Path, value: str, *, field: str) -> Path:
    root = project_root.resolve()
    candidate = (root / value).resolve()
    if not candidate.is_relative_to(root):
        raise ModelRegistryError(f"MODEL_{field}_OUTSIDE_PROJECT:{value}")
    return candidate


def _parse_model(project_root: Path, model_id: str, raw: Mapping[str, Any]) -> CanonicalModel:
    required = {
        "id",
        "display_name",
        "seed",
        "timesteps",
        "sha256",
        "policy_parameter_sha256",
        "status",
        "description",
        "asset_path",
        "asset_source",
        "observation_shape",
        "action_count",
        "simulator_profile",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ModelRegistryError(f"MODEL_FIELDS_MISSING:{model_id}:{','.join(missing)}")
    if raw["id"] != model_id:
        raise ModelRegistryError(f"MODEL_ID_MISMATCH:{model_id}:{raw['id']}")
    digest = str(raw["sha256"])
    parameter_digest = raw["policy_parameter_sha256"]
    if not SHA256_PATTERN.fullmatch(digest):
        raise ModelRegistryError(f"MODEL_SHA_INVALID:{model_id}")
    if parameter_digest is not None and not SHA256_PATTERN.fullmatch(str(parameter_digest)):
        raise ModelRegistryError(f"MODEL_PARAMETER_SHA_INVALID:{model_id}")
    observation_shape = tuple(int(value) for value in raw["observation_shape"])
    if observation_shape != (268,) or int(raw["action_count"]) != 3:
        raise ModelRegistryError(f"MODEL_SPACE_CONTRACT_INVALID:{model_id}")
    return CanonicalModel(
        id=model_id,
        display_name=str(raw["display_name"]),
        seed=int(raw["seed"]),
        timesteps=int(raw["timesteps"]),
        sha256=digest,
        policy_parameter_sha256=None if parameter_digest is None else str(parameter_digest),
        status=str(raw["status"]),
        description=str(raw["description"]),
        asset_path=_project_path(project_root, str(raw["asset_path"]), field="ASSET"),
        asset_source=str(raw["asset_source"]),
        observation_shape=observation_shape,
        action_count=int(raw["action_count"]),
        simulator_profile=_project_path(
            project_root, str(raw["simulator_profile"]), field="PROFILE"
        ),
        metadata=dict(raw),
    )


def load_model_registry(project_root: Path) -> dict[str, CanonicalModel]:
    root = project_root.resolve()
    manifest_path = root / MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        raise ModelRegistryError(f"MODEL_MANIFEST_MISSING:{manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelRegistryError("MODEL_MANIFEST_INVALID_JSON") from exc
    if set(raw) != {"schema_version", "models"} or raw["schema_version"] != 1:
        raise ModelRegistryError("MODEL_MANIFEST_SCHEMA_INVALID")
    models = raw["models"]
    if not isinstance(models, dict) or tuple(models) != MODEL_IDS:
        raise ModelRegistryError(
            f"MODEL_REGISTRY_IDS_INVALID:{tuple(models) if isinstance(models, dict) else type(models).__name__}"
        )
    return {
        model_id: _parse_model(root, model_id, models[model_id])
        for model_id in MODEL_IDS
    }


def policy_parameter_sha256(model: Any) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.policy.state_dict().items()):
        array = tensor.detach().cpu().contiguous().numpy()
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def load_canonical_model(
    project_root: Path,
    model_id: str,
    *,
    device: str = "cpu",
) -> LoadedCanonicalModel:
    registry = load_model_registry(project_root)
    if model_id not in registry:
        raise ModelRegistryError(f"UNKNOWN_MODEL_ID:{model_id}")
    spec = registry[model_id]
    if not spec.asset_path.is_file():
        raise ModelRegistryError(
            f"CANONICAL_MODEL_FILE_REQUIRED:{model_id}:{spec.asset_path}"
        )
    before = sha256_file(spec.asset_path)
    if before != spec.sha256:
        raise ModelRegistryError(f"MODEL_SHA_MISMATCH:{model_id}:{before}!={spec.sha256}")

    from stable_baselines3 import PPO

    model = PPO.load(str(spec.asset_path), device=device)
    if int(model.num_timesteps) != spec.timesteps:
        raise ModelRegistryError(
            f"MODEL_TIMESTEPS_MISMATCH:{model_id}:{model.num_timesteps}!={spec.timesteps}"
        )
    if tuple(model.observation_space.shape) != spec.observation_shape:
        raise ModelRegistryError(
            f"MODEL_OBSERVATION_SPACE_MISMATCH:{model_id}:{model.observation_space.shape}"
        )
    if int(model.action_space.n) != spec.action_count:
        raise ModelRegistryError(
            f"MODEL_ACTION_SPACE_MISMATCH:{model_id}:{model.action_space}"
        )
    parameter_digest = None
    if spec.policy_parameter_sha256 is not None:
        parameter_digest = policy_parameter_sha256(model)
        if parameter_digest != spec.policy_parameter_sha256:
            raise ModelRegistryError(
                f"MODEL_POLICY_PARAMETER_SHA_MISMATCH:{model_id}:{parameter_digest}"
            )
    after = sha256_file(spec.asset_path)
    if after != spec.sha256:
        raise ModelRegistryError(f"MODEL_CHANGED_DURING_LOAD:{model_id}:{after}")
    return LoadedCanonicalModel(
        spec=spec,
        path=spec.asset_path,
        model=model,
        policy_parameter_sha256=parameter_digest,
    )
