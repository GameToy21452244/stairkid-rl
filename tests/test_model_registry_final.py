from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from stair_agent.core.model_registry import (
    MODEL_IDS,
    ModelRegistryError,
    load_canonical_model,
    load_model_registry,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]


def test_registry_contains_exactly_two_explicit_models_and_no_default() -> None:
    registry = load_model_registry(ROOT)
    assert tuple(registry) == MODEL_IDS == ("v3", "r4")
    assert "default" not in registry
    assert "v2" not in registry
    assert "champion" not in registry
    raw = json.loads((ROOT / "models/manifest.json").read_text(encoding="utf-8"))
    for model in raw["models"].values():
        assert "policy_parameter_sha256" not in model


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_canonical_asset_sha_and_ppo_contract(model_id: str) -> None:
    spec = load_model_registry(ROOT)[model_id]
    if not spec.asset_path.is_file():
        pytest.skip(f"local canonical asset not installed: {spec.asset_path}")
    assert sha256_file(spec.asset_path) == spec.sha256
    loaded = load_canonical_model(ROOT, model_id)
    assert loaded.spec.id == model_id
    assert loaded.model.num_timesteps == spec.timesteps
    assert loaded.model.observation_space.shape == (268,)
    assert loaded.model.action_space.n == 3
    assert not hasattr(loaded, "policy_parameter_sha256")
    action, probabilities = loaded.predict_with_probabilities(
        np.zeros(268, dtype=np.float32)
    )
    assert action in (0, 1, 2)
    assert len(probabilities) == 3
    assert sum(probabilities) == pytest.approx(1.0)


def test_bad_sha_fails_closed(tmp_path: Path) -> None:
    source = json.loads((ROOT / "models/manifest.json").read_text(encoding="utf-8"))
    source["models"]["v3"]["asset_path"] = "models/cache/bad.zip"
    project = tmp_path / "project"
    (project / "models/cache").mkdir(parents=True)
    (project / "configs").mkdir()
    (project / "models/manifest.json").write_text(
        json.dumps(source), encoding="utf-8"
    )
    (project / "models/cache/bad.zip").write_bytes(b"not the canonical model")
    with pytest.raises(ModelRegistryError, match="MODEL_SHA_MISMATCH"):
        load_canonical_model(project, "v3")


def test_unknown_model_never_falls_back() -> None:
    with pytest.raises(ModelRegistryError, match="UNKNOWN_MODEL_ID"):
        load_canonical_model(ROOT, "anything-else")
