from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .physics_profile import PhysicsProfile, ObservationRandomizationConfig
from .fidelity_v3 import (
    FIDELITY_V3_VERSION,
    FidelityV3Env,
    FidelityV3Profile,
    ObservationEmulatorProfile,
)
from ..simulator.fidelity_v3_generator import V3LayoutProfile

FRESH_V3_TRAINING_LINEAGE = "fresh-random-init-v1"


def _mapping(raw: Any, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"FRESH_V3_{name}_MUST_BE_MAPPING")
    return raw


def _validate_fresh_curriculum(curriculum: dict[str, Any]) -> None:
    expected_stages = {
        "stage_a": (196_608, ("ordinary",)),
        "stage_b": (393_216, ("ordinary", "ordinary", "ordinary", "ordinary", "ordinary", "ordinary", "failure", "success")),
        "stage_c": (655_360, ("ordinary", "ordinary", "failure", "success")),
    }
    for name, (end, schedule) in expected_stages.items():
        stage = _mapping(curriculum.get(name), f"CURRICULUM_{name.upper()}")
        if int(stage.get("end_timesteps", -1)) != end:
            raise ValueError(f"FRESH_V3_{name.upper()}_END_MISMATCH")
        if tuple(map(str, stage.get("schedule_cycle", []))) != schedule:
            raise ValueError(f"FRESH_V3_{name.upper()}_SCHEDULE_MISMATCH")
    expected_scalars = {
        "bank_target_per_class": 48,
        "bank_collection_max_episodes": 256,
        "failure_snapshot_lookback_steps": 3,
        "success_min_floor": 5,
        "success_snapshots_max_per_episode": 3,
    }
    for key, value in expected_scalars.items():
        if int(curriculum.get(key, -1)) != value:
            raise ValueError(f"FRESH_V3_CURRICULUM_CONTRACT_MISMATCH:{key}")


def load_fidelity_v3_fresh_profile(path: str | Path) -> FidelityV3Profile:
    profile_path = Path(path).resolve()
    raw = _mapping(yaml.safe_load(profile_path.read_text(encoding="utf-8")), "PROFILE")
    if raw.get("fidelity_version") != FIDELITY_V3_VERSION:
        raise ValueError("FRESH_V3_FIDELITY_VERSION_MISMATCH")
    if raw.get("training_lineage") != FRESH_V3_TRAINING_LINEAGE:
        raise ValueError("FRESH_V3_TRAINING_LINEAGE_MISMATCH")
    forbidden = {"parent_fidelity_profile", "future_training_parent"} & set(raw)
    if forbidden:
        raise ValueError(f"FRESH_V3_FORBIDDEN_LEGACY_RUNTIME_DEPENDENCY:{sorted(forbidden)}")

    physics = _mapping(raw.get("physics_profile"), "PHYSICS_PROFILE")
    if "parent_fidelity_profile" in physics or "future_training_parent" in physics:
        raise ValueError("FRESH_V3_PHYSICS_PARENT_REFERENCE_FORBIDDEN")
    nominal = {str(k): float(v) for k, v in _mapping(physics.get("nominal"), "PHYSICS_NOMINAL").items()}
    ranges = {
        str(k): (float(v[0]), float(v[1]))
        for k, v in _mapping(physics.get("ranges"), "PHYSICS_RANGES").items()
    }
    observation = ObservationRandomizationConfig(**_mapping(physics.get("observation"), "PHYSICS_OBSERVATION"))
    materialized_physics = PhysicsProfile(
        nominal=nominal,
        ranges=ranges,
        observation=observation,
        dr_enabled=True,
        dr_profile="fresh_v3_materialized_real_v1",
    )

    cadence = {int(k): float(v) for k, v in _mapping(raw.get("cadence"), "CADENCE")["hz_probabilities"].items()}
    if set(cadence) != {8, 10, 12} or abs(sum(cadence.values()) - 1.0) > 1e-9:
        raise ValueError("FRESH_V3_CADENCE_MIX")

    curriculum = _mapping(raw.get("fresh_curriculum"), "CURRICULUM")
    _validate_fresh_curriculum(curriculum)

    profile = FidelityV3Profile(
        path=profile_path,
        parent=materialized_physics,
        layout=V3LayoutProfile.from_mapping(_mapping(raw.get("layout"), "LAYOUT")),
        layout_raw=_mapping(raw.get("layout"), "LAYOUT"),
        observation=ObservationEmulatorProfile.from_mapping(_mapping(raw.get("observation_emulator"), "OBSERVATION_EMULATOR")),
        cadence_probabilities=cadence,
        curriculum_cycle=("ordinary",),
        preflight_gates={},
        provenance={**_mapping(raw.get("provenance"), "PROVENANCE"), "training_lineage": FRESH_V3_TRAINING_LINEAGE},
    )
    if profile.provenance.get("policy_parent") != "NONE" or profile.provenance.get("initialization") != "RANDOM":
        raise ValueError("FRESH_V3_POLICY_PROVENANCE_INVALID")
    return profile


def load_fresh_curriculum_config(path: str | Path) -> dict[str, Any]:
    raw = _mapping(yaml.safe_load(Path(path).read_text(encoding="utf-8")), "PROFILE")
    curriculum = _mapping(raw.get("fresh_curriculum"), "CURRICULUM")
    _validate_fresh_curriculum(curriculum)
    return curriculum


def make_fidelity_v3_fresh_env(
    profile_path: str | Path,
    *,
    base_seed: int,
    forced_fps: int | None = None,
) -> FidelityV3Env:
    return FidelityV3Env(
        profile=load_fidelity_v3_fresh_profile(profile_path),
        base_seed=base_seed,
        forced_fps=forced_fps,
    )


__all__ = [
    "FRESH_V3_TRAINING_LINEAGE",
    "load_fidelity_v3_fresh_profile",
    "load_fresh_curriculum_config",
    "make_fidelity_v3_fresh_env",
]
