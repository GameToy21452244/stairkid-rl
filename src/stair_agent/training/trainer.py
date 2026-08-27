"""Single PPO trainer driven by the V3/R4 reproducibility presets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from stair_agent.core.model_registry import load_model_registry, sha256_file
from stair_agent.envs.fidelity_v3_5 import make_fidelity_v3_5_env
from stair_agent.envs.fidelity_v3_fresh import make_fidelity_v3_fresh_env
from stair_agent.evaluation import floor_metrics
from stair_agent.fresh_v3_curriculum import (
    FreshV3SelfCurriculumEnv,
    collect_self_curriculum_bank,
)
from stair_agent.v3_5_curriculum import V35TargetedCurriculumEnv
from .assets import load_training_assets, stage_r4_bundle
from .configs import TrainingTarget, load_training_target
from .manifest import git_state, initial_manifest, utc_now, write_json_atomic
from .resume import ValidatedResume, validate_resume


class TrainingError(RuntimeError):
    pass


FULL_TRAINING_AUTHORIZATION = "AUTHORIZE_STAIRKID_FULL_TRAINING"


@dataclass(frozen=True)
class TrainingRequest:
    target_id: str
    project_root: Path
    output_root: Path
    mode: str = "precheck"
    seed: int | None = None
    device: str | None = None
    resume: Path | None = None
    resume_metadata: Path | None = None
    allow_dirty: bool = False
    authorization: str = ""


def _canonical_write_guard(project_root: Path, path: Path) -> Path:
    destination = path.resolve()
    registry = load_model_registry(project_root)
    protected = {spec.asset_path.resolve() for spec in registry.values()}
    cache_root = (project_root.resolve() / "models/cache").resolve()
    if destination in protected or destination.is_relative_to(cache_root):
        raise TrainingError(f"CANONICAL_MODEL_OVERWRITE_FORBIDDEN:{destination}")
    return destination


def _profile(project_root: Path, target: TrainingTarget) -> Path:
    path = (project_root.resolve() / str(target.environment["profile"])).resolve()
    if not path.is_relative_to(project_root.resolve()) or not path.is_file():
        raise TrainingError(f"TRAINING_PROFILE_REQUIRED:{path}")
    return path


def _ordinary_factory(target_id: str, profile: Path, base_seed: int) -> Callable[[], Any]:
    if target_id == "v3":
        return lambda: make_fidelity_v3_fresh_env(profile, base_seed=base_seed)
    return lambda: make_fidelity_v3_5_env(profile, base_seed=base_seed)


def _ordinary_vec(target: TrainingTarget, profile: Path, seed: int, *, smoke: bool):
    from stable_baselines3.common.vec_env import DummyVecEnv

    count = 1 if smoke else int(target.algorithm["n_envs"])
    return DummyVecEnv(
        [
            _ordinary_factory(
                target.id,
                profile,
                1_000_000 + seed * 100_000 + index * 10_000_000,
            )
            for index in range(count)
        ]
    )


def _v3_curriculum_vec(
    profile: Path,
    seed: int,
    bank_dir: Path,
    *,
    n_envs: int,
    stage_offset: int,
):
    from stable_baselines3.common.vec_env import DummyVecEnv

    manifest = bank_dir / "manifest.json"
    return DummyVecEnv(
        [
            lambda index=index: FreshV3SelfCurriculumEnv(
                profile_path=profile,
                bank_manifest_path=manifest,
                bank_root=bank_dir,
                base_seed=50_000_000 + seed * 100_000 + stage_offset + index * 10_000_000,
            )
            for index in range(n_envs)
        ]
    )


def _r4_curriculum_vec(
    profile: Path,
    seed: int,
    bank_dir: Path,
    source_sha: str,
    *,
    n_envs: int,
):
    from stable_baselines3.common.vec_env import DummyVecEnv

    if n_envs != 4:
        raise TrainingError("R4_FIXED_VECTOR_LANES_REQUIRE_FOUR_ENVS")
    manifest = bank_dir / "manifest.json"
    modes = ("ordinary", "ordinary", "failure", "success")
    factories: list[Callable[[], Any]] = []
    for index, mode in enumerate(modes):
        base_seed = 70_000_000 + seed * 100_000 + index * 10_000_000
        if mode == "ordinary":
            factories.append(
                lambda base_seed=base_seed: make_fidelity_v3_5_env(
                    profile, base_seed=base_seed
                )
            )
        else:
            factories.append(
                lambda base_seed=base_seed, mode=mode: V35TargetedCurriculumEnv(
                    profile_path=profile,
                    bank_root=bank_dir,
                    bank_manifest_path=manifest,
                    base_seed=base_seed,
                    expected_policy_seed=seed,
                    expected_source_sha256=source_sha,
                    fixed_mode=mode,
                    expected_source_timesteps=589_824,
                )
            )
    return DummyVecEnv(factories)


def _new_model(target: TrainingTarget, env: Any, seed: int, device: str, *, smoke: bool):
    from stable_baselines3 import PPO

    algorithm = target.algorithm
    return PPO(
        str(algorithm["policy"]),
        env,
        learning_rate=float(algorithm["learning_rate"]),
        n_steps=8 if smoke else int(algorithm["n_steps"]),
        batch_size=8 if smoke else int(algorithm["batch_size"]),
        n_epochs=1 if smoke else int(algorithm["n_epochs"]),
        gamma=float(algorithm["gamma"]),
        gae_lambda=float(algorithm["gae_lambda"]),
        clip_range=float(algorithm["clip_range"]),
        ent_coef=float(algorithm["ent_coef"]),
        vf_coef=float(algorithm["vf_coef"]),
        max_grad_norm=float(algorithm["max_grad_norm"]),
        seed=seed,
        device=device,
        verbose=0,
    )


def _save_model(model: Any, path: Path) -> tuple[Path, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".partial.zip")
    temporary.unlink(missing_ok=True)
    model.save(temporary)
    if not temporary.is_file():
        raise TrainingError("TRAINING_CHECKPOINT_SAVE_FAILED")
    temporary.replace(path)
    return path, sha256_file(path)


def _evaluate(model: Any, target: TrainingTarget, profile: Path) -> dict[str, Any]:
    evaluation = target.raw["evaluation"]
    start = int(evaluation["dev_seed_start"])
    count = int(evaluation["dev_episodes"])
    seconds = float(evaluation["physical_seconds"])
    floors: list[int] = []
    env_factory = _ordinary_factory(target.id, profile, start)
    env = env_factory()
    try:
        for episode_seed in range(start, start + count):
            observation, _ = env.reset(seed=episode_seed)
            terminated = truncated = False
            steps = 0
            max_steps = max(1, int(seconds * env.config.fps))
            while not (terminated or truncated) and steps < max_steps:
                action, _ = model.predict(observation, deterministic=True)
                observation, _, terminated, truncated, _ = env.step(
                    int(np.asarray(action).item())
                )
                steps += 1
            floors.append(int(env.simulator.deepest_floor))
    finally:
        env.close()
    return {"deterministic": True, "floors": floors, "metrics": floor_metrics(floors)}


def _resolved_run_dir(request: TrainingRequest, target: TrainingTarget, seed: int) -> Path:
    root = _canonical_write_guard(request.project_root, request.output_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{target.id}-{request.mode}-seed{seed}-{stamp}"
    return root / target.id / run_id


def _write_resolved_config(run_dir: Path, target: TrainingTarget) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "checkpoints").mkdir()
    (run_dir / "evaluation").mkdir()
    (run_dir / "logs").mkdir()
    (run_dir / "config_resolved.yaml").write_text(
        yaml.safe_dump(dict(target.raw), sort_keys=False), encoding="utf-8"
    )


def _precheck(request: TrainingRequest, target: TrainingTarget) -> dict[str, Any]:
    commit, dirty = git_state(request.project_root)
    if dirty and not request.allow_dirty:
        raise TrainingError("TRAINING_REQUIRES_CLEAN_GIT_WORKTREE")
    profile = _profile(request.project_root, target)
    env = _ordinary_vec(target, profile, target.default_seed, smoke=True)
    try:
        if tuple(env.observation_space.shape) != target.observation_shape:
            raise TrainingError("TRAINING_ENV_OBSERVATION_MISMATCH")
        if int(env.action_space.n) != target.action_count:
            raise TrainingError("TRAINING_ENV_ACTION_MISMATCH")
    finally:
        env.close()
    required_assets = list(target.raw["assets"]["required"])
    asset_registry = load_training_assets(request.project_root)
    assets = []
    for asset_id in required_assets:
        asset = asset_registry[asset_id]
        assets.append(
            {
                "asset_id": asset.id,
                "sha256": asset.sha256,
                "available": asset.cache_path.is_file()
                and sha256_file(asset.cache_path) == asset.sha256,
            }
        )
    missing_assets = [item["asset_id"] for item in assets if not item["available"]]
    if missing_assets and request.mode != "smoke":
        raise TrainingError(f"REQUIRED_TRAINING_ASSETS_MISSING:{missing_assets}")
    return {
        "status": "PASS",
        "git_commit": commit,
        "git_dirty": dirty,
        "target": target.id,
        "config_sha256": target.config_sha256,
        "observation_space": list(target.observation_shape),
        "action_space": f"Discrete({target.action_count})",
        "required_assets": assets,
        "output_root": str(request.output_root.resolve()),
    }


def _smoke(request: TrainingRequest, target: TrainingTarget, precheck: dict[str, Any]) -> dict[str, Any]:
    seed = request.seed if request.seed is not None else target.default_seed
    device = request.device or str(target.algorithm["device"])
    profile = _profile(request.project_root, target)
    run_dir = _resolved_run_dir(request, target, seed)
    _write_resolved_config(run_dir, target)
    canonical = load_model_registry(request.project_root)
    before = {model_id: sha256_file(spec.asset_path) for model_id, spec in canonical.items()}
    mismatched = [
        model_id
        for model_id, spec in canonical.items()
        if before[model_id] != spec.sha256
    ]
    if mismatched:
        raise TrainingError(f"CANONICAL_MODEL_SHA_MISMATCH:{mismatched}")
    source_model = None
    source_sha = None
    env = _ordinary_vec(target, profile, seed, smoke=True)
    try:
        if target.id == "v3":
            model = _new_model(target, env, seed, device, smoke=True)
            start = 0
        else:
            source = canonical["r4"]
            validated = validate_resume(
                source.asset_path,
                target,
                env=env,
                device=device,
                allow_pinned_external=True,
            )
            start = validated.current_timesteps
            source_model = str(source.asset_path)
            source_sha = source.sha256
            model = _new_model(target, env, seed, device, smoke=True)
            model.policy.load_state_dict(validated.model.policy.state_dict())
            model.num_timesteps = start
        model.learn(total_timesteps=8, reset_num_timesteps=False)
        output, output_sha = _save_model(
            model, run_dir / "checkpoints" / f"smoke_{int(model.num_timesteps)}.zip"
        )
    finally:
        env.close()
    after = {model_id: sha256_file(spec.asset_path) for model_id, spec in canonical.items()}
    if after != before:
        raise TrainingError("CANONICAL_MODEL_CHANGED_DURING_SMOKE")
    manifest = initial_manifest(
        run_id=run_dir.name,
        target_id=target.id,
        git_commit=precheck["git_commit"],
        git_dirty=precheck["git_dirty"],
        device=device,
        seed=seed,
        start_timesteps=start,
        target_timesteps=start + 8,
        config_sha256=target.config_sha256,
        source_model=source_model,
        source_model_sha256=source_sha,
        training_assets=precheck["required_assets"],
        training_performed="SMOKE_ONLY",
    )
    manifest.update(
        {
            "completed_at": utc_now(),
            "output_checkpoint": str(output),
            "output_sha256": output_sha,
            "actual_timesteps": int(model.num_timesteps),
            "canonical_models_unchanged": True,
        }
    )
    write_json_atomic(run_dir / "training_manifest.json", manifest)
    return {"status": "PASS", "mode": "smoke", "run_dir": str(run_dir), "manifest": manifest}


def _full(request: TrainingRequest, target: TrainingTarget, precheck: dict[str, Any]) -> dict[str, Any]:
    seed = request.seed if request.seed is not None else target.default_seed
    if seed not in tuple(int(value) for value in target.algorithm["seed_candidates"]):
        raise TrainingError("TRAINING_SEED_NOT_IN_PRESET")
    device = request.device or str(target.algorithm["device"])
    profile = _profile(request.project_root, target)
    run_dir = _resolved_run_dir(request, target, seed)
    _write_resolved_config(run_dir, target)
    asset_rows = precheck["required_assets"]
    source_model = None
    source_sha = None

    if target.id == "r4":
        stage = stage_r4_bundle(request.project_root)
        source_path = stage / f"seed_{seed}/checkpoints/v3_5_589824.zip"
        frozen_source_sha = sha256_file(source_path)
        bank_dir = stage / f"banks/seed_{seed}/r1_targeted"
        env = _r4_curriculum_vec(
            profile,
            seed,
            bank_dir,
            frozen_source_sha,
            n_envs=int(target.algorithm["n_envs"]),
        )
        validated = validate_resume(
            request.resume or source_path,
            target,
            env=env,
            metadata_path=request.resume_metadata,
            device=device,
            allow_pinned_external=request.resume is None,
        )
        model = validated.model
        start = validated.current_timesteps
        source_model = str(validated.path)
        source_sha = validated.sha256
    else:
        env = _ordinary_vec(target, profile, seed, smoke=False)
        if request.resume is not None:
            validated = validate_resume(
                request.resume,
                target,
                env=env,
                metadata_path=request.resume_metadata,
                device=device,
            )
            model = validated.model
            start = validated.current_timesteps
            source_model = str(validated.path)
            source_sha = validated.sha256
            resume_run = validated.path.parent.parent
            if 196_608 < start < 393_216:
                bank_dir = resume_run / "banks" / f"seed_{seed}" / "stage_a_to_b"
                env.close()
                env = _v3_curriculum_vec(
                    profile, seed, bank_dir, n_envs=4, stage_offset=0
                )
                model.set_env(env)
            elif start > 393_216:
                bank_dir = resume_run / "banks" / f"seed_{seed}" / "stage_b_to_c"
                env.close()
                env = _v3_curriculum_vec(
                    profile, seed, bank_dir, n_envs=4, stage_offset=5_000_000
                )
                model.set_env(env)
        else:
            model = _new_model(target, env, seed, device, smoke=False)
            start = 0

    manifest = initial_manifest(
        run_id=run_dir.name,
        target_id=target.id,
        git_commit=precheck["git_commit"],
        git_dirty=precheck["git_dirty"],
        device=device,
        seed=seed,
        start_timesteps=start,
        target_timesteps=target.total_timesteps,
        config_sha256=target.config_sha256,
        source_model=source_model,
        source_model_sha256=source_sha,
        training_assets=asset_rows,
        training_performed="FULL",
    )
    write_json_atomic(run_dir / "training_manifest.json", manifest)
    checkpoints = [
        int(value)
        for value in target.training["checkpoint_targets"]
        if int(value) > int(model.num_timesteps)
    ]
    latest_output = None
    latest_sha = None
    try:
        for checkpoint in checkpoints:
            current = int(model.num_timesteps)
            if target.id == "v3":
                if current == 196_608:
                    checkpoint_path = run_dir / "checkpoints/fresh_v3_196608.zip"
                    if not checkpoint_path.is_file() and request.resume is not None:
                        checkpoint_path = request.resume.resolve()
                    bank_dir = run_dir / "banks" / f"seed_{seed}" / "stage_a_to_b"
                    collect_self_curriculum_bank(
                        model=model,
                        profile_path=profile,
                        output_dir=bank_dir,
                        policy_seed=seed,
                        source_model_sha256=sha256_file(checkpoint_path),
                        source_model_timesteps=196_608,
                        collection_seed_base=20_000_000 + seed * 100_000,
                        stage_label=f"seed_{seed}_stage_a_to_b",
                        schedule_cycle=tuple(target.training["stages"][1]["schedule"]),
                        target_per_class=int(target.raw["curriculum"]["target_per_class"]),
                        max_episodes=int(target.raw["curriculum"]["collection_max_episodes"]),
                        failure_lookback_steps=int(target.raw["curriculum"]["failure_snapshot_lookback_steps"]),
                        success_min_floor=int(target.raw["curriculum"]["success_min_floor"]),
                        success_snapshots_max_per_episode=int(target.raw["curriculum"]["success_snapshots_max_per_episode"]),
                    )
                    env.close()
                    env = _v3_curriculum_vec(profile, seed, bank_dir, n_envs=4, stage_offset=0)
                    model.set_env(env)
                elif current == 393_216:
                    checkpoint_path = run_dir / "checkpoints/fresh_v3_393216.zip"
                    if not checkpoint_path.is_file() and request.resume is not None:
                        checkpoint_path = request.resume.resolve()
                    bank_dir = run_dir / "banks" / f"seed_{seed}" / "stage_b_to_c"
                    collect_self_curriculum_bank(
                        model=model,
                        profile_path=profile,
                        output_dir=bank_dir,
                        policy_seed=seed,
                        source_model_sha256=sha256_file(checkpoint_path),
                        source_model_timesteps=393_216,
                        collection_seed_base=25_000_000 + seed * 100_000,
                        stage_label=f"seed_{seed}_stage_b_to_c",
                        schedule_cycle=tuple(target.training["stages"][2]["schedule"]),
                        target_per_class=int(target.raw["curriculum"]["target_per_class"]),
                        max_episodes=int(target.raw["curriculum"]["collection_max_episodes"]),
                        failure_lookback_steps=int(target.raw["curriculum"]["failure_snapshot_lookback_steps"]),
                        success_min_floor=int(target.raw["curriculum"]["success_min_floor"]),
                        success_snapshots_max_per_episode=int(target.raw["curriculum"]["success_snapshots_max_per_episode"]),
                    )
                    env.close()
                    env = _v3_curriculum_vec(profile, seed, bank_dir, n_envs=4, stage_offset=5_000_000)
                    model.set_env(env)
            remaining = checkpoint - int(model.num_timesteps)
            quantum = int(target.training["rollout_quantum"])
            if remaining <= 0 or remaining % quantum:
                raise TrainingError(f"TRAINING_REMAINING_STEPS_INVALID:{remaining}")
            model.learn(total_timesteps=remaining, reset_num_timesteps=False)
            filename = (
                f"fresh_v3_{checkpoint}.zip"
                if target.id == "v3"
                else f"v3_5_{checkpoint}.zip"
            )
            latest_output, latest_sha = _save_model(
                model, run_dir / "checkpoints" / filename
            )
            sidecar = {
                "training_target": target.id,
                "config_sha256": target.config_sha256,
                "num_timesteps": int(model.num_timesteps),
                "output_sha256": latest_sha,
                "policy_seed": seed,
            }
            write_json_atomic(latest_output.with_suffix(".training.json"), sidecar)
            write_json_atomic(
                run_dir / "evaluation" / f"t{checkpoint}.json",
                _evaluate(model, target, profile),
            )
    finally:
        env.close()
    manifest.update(
        {
            "completed_at": utc_now(),
            "output_checkpoint": None if latest_output is None else str(latest_output),
            "output_sha256": latest_sha,
            "actual_timesteps": int(model.num_timesteps),
        }
    )
    write_json_atomic(run_dir / "training_manifest.json", manifest)
    return {"status": "PASS", "mode": "full", "run_dir": str(run_dir), "manifest": manifest}


def run_training(request: TrainingRequest) -> dict[str, Any]:
    if request.mode not in {"precheck", "smoke", "full"}:
        raise TrainingError(f"TRAINING_MODE_INVALID:{request.mode}")
    if (
        request.mode == "full"
        and request.authorization != FULL_TRAINING_AUTHORIZATION
    ):
        raise TrainingError("FULL_TRAINING_NOT_AUTHORIZED")
    root = request.project_root.resolve()
    target = load_training_target(root, request.target_id)
    precheck = _precheck(request, target)
    if request.mode == "precheck":
        return precheck
    if request.mode == "smoke":
        return _smoke(request, target, precheck)
    return _full(request, target, precheck)
