"""Source-level verification for the final active project surface."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from stair_agent.config import AppConfig
from stair_agent.core.model_registry import MODEL_IDS, load_canonical_model, load_model_registry
from stair_agent.sim.runtime import create_simulator_environment
from stair_agent.simulator.scenarios import configure_flipping_landing
from stair_agent.training.assets import load_training_assets
from stair_agent.training.configs import TARGET_IDS, load_training_registry


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/StairKid_Training_Colab.ipynb"


def _verify_notebook() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    if notebook.get("nbformat") != 4:
        raise RuntimeError("NOTEBOOK_FORMAT_INVALID")
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") == "code":
            ast.parse("".join(cell.get("source", [])), filename=f"cell_{index}")


def _verify_active_surface() -> None:
    paths = [
        *sorted((ROOT / "scripts").glob("*.py")),
        *sorted((ROOT / "src/stair_agent").rglob("*.py")),
        *sorted((ROOT / "configs").rglob("*.yaml")),
        *sorted((ROOT / "notebooks").glob("*.ipynb")),
        *sorted((ROOT / ".github/workflows").glob("*.yml")),
    ]
    forbidden = (
        "1e29770fb8514014b3dc10e4ba6a1ff5"
        "078a59515ceb0dc3eb73b7ca6f03f521",
        "hybridlandingrouter",
        "expected_v2_sha256",
        "frozen_v2",
        "source-package handoff",
        "project_source_zip",
        "--resume-sha256",
        "resume_sha256",
        "policy_parameter_sha256",
        "source_tree_fingerprint",
        "project_source_fingerprint",
    )
    for path in paths:
        if path.resolve() == Path(__file__).resolve():
            continue
        source = path.read_text(encoding="utf-8").casefold()
        if any(value in source for value in forbidden):
            raise RuntimeError(f"OBSOLETE_ACTIVE_DEPENDENCY:{path}")


def _verify_simulator_contract() -> None:
    for model_id in MODEL_IDS:
        env = create_simulator_environment(
            ROOT, model_id, base_seed=12345, render_mode=None
        )
        try:
            observation, _ = env.reset(seed=12345)
            if observation.shape != (268,) or env.action_space.n != 3:
                raise RuntimeError(f"SIMULATOR_CONTRACT_INVALID:{model_id}")
            if env.config.physics_hz != 60:
                raise RuntimeError(f"SIMULATOR_PHYSICS_HZ_INVALID:{model_id}")
            if model_id == "r4":
                floor = configure_flipping_landing(env.simulator, active=False)
                platform = next(
                    item for item in env.simulator.platforms
                    if item.floor_index == floor
                )
                env.simulator.elapsed_seconds = 100.0
                if env.simulator.platform_is_active(platform):
                    raise RuntimeError("FLIPPING_GLOBAL_ELAPSED_OVERRIDE_PRESENT")
        finally:
            env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        action="store_true",
        help="Also require and load both external canonical checkpoints.",
    )
    args = parser.parse_args()
    models = load_model_registry(ROOT)
    targets = load_training_registry(ROOT)
    assets = load_training_assets(ROOT)
    if tuple(models) != MODEL_IDS or tuple(targets) != TARGET_IDS:
        raise RuntimeError("ACTIVE_REGISTRY_CONTRACT_INVALID")
    model_manifest = json.loads(
        (ROOT / "models/manifest.json").read_text(encoding="utf-8")
    )
    if any(
        "policy_parameter_sha256" in row
        for row in model_manifest["models"].values()
    ):
        raise RuntimeError("POLICY_PARAMETER_SHA_RUNTIME_GATE_PRESENT")
    if tuple(assets) != ("r4_frozen_r1_bundle",):
        raise RuntimeError("TRAINING_ASSET_TOP_LEVEL_GATE_INVALID")
    AppConfig.load(ROOT / "config.example.yaml")
    _verify_notebook()
    _verify_active_surface()
    _verify_simulator_contract()
    if args.models:
        for model_id in MODEL_IDS:
            loaded = load_canonical_model(ROOT, model_id)
            print(f"MODEL_{model_id.upper()}_SHA256={loaded.spec.sha256}")
            print(f"MODEL_{model_id.upper()}_LOAD=PASS")
    print(f"MODEL_IDS={','.join(models)}")
    print(f"TRAINING_TARGETS={','.join(targets)}")
    print(f"TRAINING_ASSETS={len(assets)}")
    print("REAL_CONFIG=PASS")
    print("SIMULATOR_CONTRACT=PASS")
    print("CORRECTED_FLIPPING_IDENTITY=PASS")
    print("OBSOLETE_ACTIVE_DEPENDENCIES=NONE")
    print("SIMPLIFIED_SHA_POLICY=PASS")
    print("NOTEBOOK=PASS")
    print("PROJECT_SOURCE_VERIFY=PASS")
    print("REAL_GAME_EXECUTED=NO")
    print("TRAINING_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
