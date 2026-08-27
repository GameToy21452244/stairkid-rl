"""Source-level verification for the final active project surface."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from stair_agent.core.model_registry import MODEL_IDS, load_canonical_model, load_model_registry
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
    _verify_notebook()
    if args.models:
        for model_id in MODEL_IDS:
            loaded = load_canonical_model(ROOT, model_id)
            print(f"MODEL_{model_id.upper()}_SHA256={loaded.spec.sha256}")
            print(f"MODEL_{model_id.upper()}_LOAD=PASS")
    print(f"MODEL_IDS={','.join(models)}")
    print(f"TRAINING_TARGETS={','.join(targets)}")
    print(f"TRAINING_ASSETS={len(assets)}")
    print("NOTEBOOK=PASS")
    print("PROJECT_SOURCE_VERIFY=PASS")
    print("REAL_GAME_EXECUTED=NO")
    print("TRAINING_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
