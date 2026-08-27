from __future__ import annotations

import ast
from pathlib import Path

import pytest

from stair_agent.core.model_registry import MODEL_IDS, load_model_registry
from stair_agent.real.runtime import prepare_real_dry_run


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_REAL_FILES = (
    ROOT / "src/stair_agent/real/runtime.py",
    ROOT / "scripts/run_real_agent.py",
)


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_real_dry_run_builds_perception_only_and_sends_zero_actions(model_id: str) -> None:
    spec = load_model_registry(ROOT)[model_id]
    if not spec.asset_path.is_file():
        pytest.skip(f"local canonical asset not installed: {spec.asset_path}")
    result = prepare_real_dry_run(ROOT, model_id)
    assert result.loaded_model.spec.id == model_id
    assert result.loaded_model.model.observation_space.shape == (268,)
    assert result.loaded_model.model.action_space.n == 3
    assert result.actions_sent == 0
    assert result.capture_constructed is False
    assert result.controller_constructed is False
    assert result.frame_pipeline is not None


def test_active_real_entrypoint_has_no_v2_hybrid_or_input_backend_dependency() -> None:
    forbidden_text = ("frozen_v2", "hybridlandingrouter", "expected_v2_sha256")
    forbidden_imports = {
        "stair_agent.input_controller",
        "stair_agent.live_env",
        "stair_agent.screen_capture",
        "stair_agent.window_manager",
        "pydirectinput",
        "pyautogui",
    }
    for path in ACTIVE_REAL_FILES:
        source = path.read_text(encoding="utf-8")
        assert not any(value in source.casefold() for value in forbidden_text)
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert imported.isdisjoint(forbidden_imports)


def test_real_cli_requires_explicit_model_and_dry_run() -> None:
    text = (ROOT / "scripts/run_real_agent.py").read_text(encoding="utf-8")
    assert 'add_argument("--model", required=True' in text
    assert "--dry-run and --control are mutually exclusive" in text
    assert "AUTHORIZE_{spec.id.upper()}_REAL_CONTROL" in text
