from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/StairKid_Training_Colab.ipynb"


def _notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _source_text() -> str:
    return "\n".join(
        "".join(cell.get("source", [])) for cell in _notebook()["cells"]
    )


def test_unified_notebook_json_and_code_cells_compile() -> None:
    notebook = _notebook()
    assert notebook["nbformat"] == 4
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]), filename=f"cell_{index}")


def test_notebook_clones_git_and_does_not_use_project_source_zip() -> None:
    text = _source_text().casefold()
    assert '"git", "clone"' in text
    assert '"git", "checkout"' in text
    assert '"-m", "pip", "install", "-e", ".[rl]"' in text
    assert "project source zip" not in text
    assert "source archive" not in text
    assert "sys.path.insert" not in text
    assert "c:\\" not in text


def test_notebook_has_single_precheck_and_full_authorization_guard() -> None:
    text = _source_text()
    assert "STAIRKID_TRAINING_PRECHECK=PASS" in text
    assert "AUTHORIZE_STAIRKID_FULL_TRAINING" in text
    assert "FULL_TRAINING_NOT_AUTHORIZED" in text
    assert "scripts/train.py" in text
    assert ".learn(" not in text


def test_notebook_supports_exact_ref_drive_resume_and_two_targets() -> None:
    text = _source_text()
    for required in (
        'TRAIN_TARGET = "v3"',
        'GIT_REF = "main"',
        "RESOLVED_COMMIT",
        "OUTPUT_TO_DRIVE",
        "DRIVE_OUTPUT_ROOT",
        "RESUME_CHECKPOINT",
        '{"v3", "r4"}',
    ):
        assert required in text
