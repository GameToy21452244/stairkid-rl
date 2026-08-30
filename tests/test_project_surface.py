from __future__ import annotations

import ast
import json
from pathlib import Path

from stair_agent.core.contracts import (
    ActionTiming,
    OBSERVATION_DIM,
    OBSERVATION_SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SCRIPTS = {
    "bulk_real_evaluation.py",
    "evaluate.py",
    "fetch_models.py",
    "fetch_training_assets.py",
    "play_simulator.py",
    "run_real_agent.py",
    "run_real_model_launcher.py",
    "run_simulator_agent.py",
    "train.py",
    "verify_project.py",
}


def test_active_script_surface_is_exact() -> None:
    assert {path.name for path in (ROOT / "scripts").glob("*.py")} == ACTIVE_SCRIPTS


def test_only_unified_notebook_is_active() -> None:
    notebooks = list((ROOT / "notebooks").glob("*.ipynb"))
    assert [path.name for path in notebooks] == ["StairKid_Training_Colab.ipynb"]
    raw = json.loads(notebooks[0].read_text(encoding="utf-8"))
    for index, cell in enumerate(raw["cells"]):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]), filename=f"cell_{index}")


def test_shared_runtime_contracts_are_current() -> None:
    assert OBSERVATION_DIM == 268
    assert OBSERVATION_SCHEMA_VERSION == "stair-observation-v3-268"
    timing = ActionTiming(1.0, 1.1, 1.2, True, 100.0)
    assert timing.action_applied is True


def test_obsolete_real_training_modules_are_absent() -> None:
    package = ROOT / "src/stair_agent"
    for name in (
        "baseline_policy.py",
        "rl_evaluation.py",
        "rl_training.py",
        "session_controller.py",
        "trajectory.py",
    ):
        assert not (package / name).exists()
