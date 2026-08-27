from __future__ import annotations

import json
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces

from stair_agent.core.model_registry import load_model_registry, sha256_file
from stair_agent.training.assets import (
    TrainingAsset,
    TrainingAssetError,
    load_training_assets,
    verify_asset,
)
from stair_agent.training.configs import (
    TARGET_IDS,
    TrainingConfigError,
    load_training_registry,
    load_training_target,
)
from stair_agent.training.manifest import initial_manifest
from stair_agent.training.resume import ResumeValidationError, validate_resume
from stair_agent.training.trainer import (
    TrainingError,
    TrainingRequest,
    _canonical_write_guard,
    run_training,
)


ROOT = Path(__file__).resolve().parents[1]


def test_training_registry_contains_exactly_v3_and_r4() -> None:
    registry = load_training_registry(ROOT)
    assert tuple(registry) == TARGET_IDS == ("v3", "r4")
    for forbidden in ("v2", "r1", "r2", "r3", "r5", "r6"):
        assert forbidden not in registry


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_training_configs_parse_and_keep_model_contract(target_id: str) -> None:
    target = load_training_target(ROOT, target_id)
    assert target.observation_shape == (268,)
    assert target.action_count == 3
    assert target.algorithm["name"] == "PPO"
    assert target.algorithm["policy"] == "MlpPolicy"
    assert target.raw["provenance"]["unresolved_fields"] == []


def test_r4_edge_penalty_and_frozen_inputs_are_exact() -> None:
    target = load_training_target(ROOT, "r4")
    assert target.raw["reward"]["edge_landing_penalty"] == 1.10
    assert target.raw["curriculum"]["r1_retraining_forbidden"] is True
    assert target.raw["curriculum"]["bank_recollection_forbidden"] is True
    assert target.training["checkpoint_targets"] == [589824, 655360, 720896]


def test_training_asset_manifest_preserves_all_known_pins() -> None:
    assets = load_training_assets(ROOT)
    assert assets["r4_frozen_r1_bundle"].sha256 == "3b8e85d52d94b11cacf1466019558670791471a190d79b80ed18a62985b7f53e"
    assert assets["r4_seed117_r1_checkpoint"].sha256 == "d25dacc88b65563b392b18f3264747e665411116197268d5e5344972b4f1ca0a"
    assert assets["r4_seed142_r1_checkpoint"].sha256 == "4f105b391a3e6dbf6ae88a4ff85c2e229dac025f9ab7eadb48862db369995b59"
    assert assets["r4_seed117_bank_manifest"].sha256 == "1609cbe829ecd66de6bf47cc195bf2e7db60f2efdd8e40791d8b906472e62def"
    assert assets["r4_seed142_bank_manifest"].sha256 == "547f8ae66409799def75cbfab81c67f28188844cf93009ae0acf26fbc31bdc40"


def test_invalid_training_asset_sha_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "asset.zip"
    path.write_bytes(b"wrong")
    asset = TrainingAsset(
        "test",
        path.name,
        "0" * 64,
        "test",
        ("r4",),
        {},
        path,
        True,
    )
    with pytest.raises(TrainingAssetError, match="SHA_MISMATCH"):
        verify_asset(asset)


def test_r4_resume_uses_existing_timesteps_not_target_as_increment() -> None:
    target = load_training_target(ROOT, "r4")
    spec = load_model_registry(ROOT)["r4"]
    if not spec.asset_path.is_file():
        pytest.skip("canonical R4 cache asset not installed")
    from stair_agent.envs.fidelity_v3_5 import make_fidelity_v3_5_env

    env = make_fidelity_v3_5_env(ROOT / "configs/fidelity_v3_5.yaml", base_seed=7)
    try:
        result = validate_resume(
            spec.asset_path,
            target,
            env=env,
            expected_sha256=spec.sha256,
            allow_pinned_external=True,
        )
    finally:
        env.close()
    assert result.current_timesteps == 655360
    assert result.target_timesteps == 720896
    assert result.remaining_timesteps == 65536


class WrongObservationEnv(gym.Env):
    def __init__(self) -> None:
        self.observation_space = spaces.Box(-1, 1, shape=(8,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(8, dtype=np.float32), {}

    def step(self, action):
        return np.zeros(8, dtype=np.float32), 0.0, False, False, {}


def test_resume_incompatible_observation_fails_closed(tmp_path: Path) -> None:
    from stable_baselines3 import PPO
    from stair_agent.envs.fidelity_v3_fresh import make_fidelity_v3_fresh_env

    wrong = WrongObservationEnv()
    checkpoint = tmp_path / "wrong.zip"
    PPO("MlpPolicy", wrong, n_steps=8, batch_size=8, n_epochs=1, verbose=0).save(checkpoint)
    correct = make_fidelity_v3_fresh_env(ROOT / "configs/fidelity_v3_fresh.yaml", base_seed=9)
    try:
        with pytest.raises(ResumeValidationError, match="INCOMPATIBLE"):
            validate_resume(
                checkpoint,
                load_training_target(ROOT, "v3"),
                env=correct,
                allow_pinned_external=True,
            )
    finally:
        correct.close()
        wrong.close()


def test_canonical_model_overwrite_guard() -> None:
    for spec in load_model_registry(ROOT).values():
        with pytest.raises(TrainingError, match="OVERWRITE_FORBIDDEN"):
            _canonical_write_guard(ROOT, spec.asset_path)


def test_training_manifest_contains_reproducibility_fields() -> None:
    manifest = initial_manifest(
        run_id="smoke",
        target_id="v3",
        git_commit="a" * 40,
        git_dirty=False,
        device="cpu",
        seed=17,
        start_timesteps=0,
        target_timesteps=8,
        config_sha256="b" * 64,
        source_model=None,
        source_model_sha256=None,
        training_assets=[],
        training_performed="SMOKE_ONLY",
    )
    for field in (
        "git_commit",
        "git_dirty",
        "python_version",
        "torch_version",
        "stable_baselines3_version",
        "observation_space",
        "action_space",
        "training_performed",
    ):
        assert field in manifest


def test_dirty_worktree_fails_without_explicit_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "stair_agent.training.trainer.git_state", lambda _root: ("a" * 40, True)
    )
    with pytest.raises(TrainingError, match="CLEAN_GIT_WORKTREE"):
        run_training(
            TrainingRequest("v3", ROOT, tmp_path, mode="precheck")
        )


def test_shared_trainer_rejects_unauthorized_full_training(tmp_path: Path) -> None:
    with pytest.raises(TrainingError, match="FULL_TRAINING_NOT_AUTHORIZED"):
        run_training(
            TrainingRequest("v3", ROOT, tmp_path, mode="full", allow_dirty=True)
        )


@pytest.mark.parametrize("target_id", TARGET_IDS)
def test_tiny_training_smoke_writes_isolated_manifest(
    target_id: str, tmp_path: Path
) -> None:
    before = {
        model_id: sha256_file(spec.asset_path)
        for model_id, spec in load_model_registry(ROOT).items()
    }
    result = run_training(
        TrainingRequest(
            target_id,
            ROOT,
            tmp_path,
            mode="smoke",
            allow_dirty=True,
        )
    )
    manifest_path = Path(result["run_dir"]) / "training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["training_performed"] == "SMOKE_ONLY"
    assert manifest["git_commit"]
    assert manifest["actual_timesteps"] == manifest["target_timesteps"]
    assert manifest["canonical_models_unchanged"] is True
    after = {
        model_id: sha256_file(spec.asset_path)
        for model_id, spec in load_model_registry(ROOT).items()
    }
    assert after == before
