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


def test_notebook_contains_training_instead_of_delegating_to_cli() -> None:
    text = _source_text()
    assert "STAIRKID_TRAINING_PRECHECK=PASS" in text
    assert "AUTHORIZE_STAIRKID_FULL_TRAINING" in text
    assert "FULL_TRAINING_NOT_AUTHORIZED" in text
    assert "scripts/train.py" not in text
    assert "subprocess.run(train_cmd" not in text
    assert "model = PPO(" in text
    assert text.count("model.learn(") >= 2


def test_notebook_makes_both_training_flows_and_outputs_visible() -> None:
    text = _source_text()
    for required in (
        "create_ppo_model",
        "run_smoke",
        "run_full",
        "activate_v3_curriculum_at_boundary",
        "collect_self_curriculum_bank",
        "stage_and_validate_r4_bundle",
        'modes = ("ordinary", "ordinary", "failure", "success")',
        "evaluate_checkpoint",
        "save_checkpoint",
        "make_training_manifest",
        "CANONICAL_MODEL_OVERWRITE_FORBIDDEN",
    ):
        assert required in text


def test_notebook_shows_r4_bundle_structural_validation() -> None:
    text = _source_text()
    for required in (
        "R4_BUNDLE_SHA",
        "archive.testzip()",
        "safe_zip_member",
        "R4_CHECKPOINT_PAIRING_INVALID",
        "validate_v35_targeted_bank",
        "expected_policy_seed=seed",
        "expected_source_sha256=checkpoint_sha",
        "expected_source_timesteps=589824",
    ):
        assert required in text


def test_notebook_supports_exact_ref_drive_resume_and_two_targets() -> None:
    text = _source_text()
    for required in (
        'TRAIN_TARGET = "v3"',
        'TRAINING_MODE = "precheck"',
        'GIT_REF = "main"',
        "RESOLVED_COMMIT",
        "OUTPUT_TO_DRIVE",
        "DRIVE_OUTPUT_ROOT",
        "RESUME_CHECKPOINT",
        '{"v3", "r4"}',
    ):
        assert required in text
    assert "RESUME_SHA256" not in text
    assert "--resume-sha256" not in text


def test_notebook_keeps_space_and_model_identity_contracts() -> None:
    text = _source_text()
    assert "EXPECTED_OBSERVATION_SHAPE = (268,)" in text
    assert "EXPECTED_ACTION_COUNT = 3" in text
    assert "e539ad8e9a39991d738ef9d4113968d933d4f2535e3b08fabe27f3b4ffd9f51e" in text
    assert "6a9e966ae69c1b3f5610bc5c8a009dcc5519e94fa20d754e54ef0ac445399e10" in text
    assert "policy_parameter_sha" not in text.casefold()


def test_notebook_consumes_single_bundle_gate_from_manifest() -> None:
    text = _source_text()
    bundle_sha = "3b8e85d52d94b11cacf1466019558670791471a190d79b80ed18a62985b7f53e"
    assert bundle_sha not in text
    assert 'TRAINING_ASSET_MANIFEST_PATH = PROJECT_ROOT / "training_assets/manifest.json"' in text
    assert 'R4_BUNDLE_SHA = str(R4_BUNDLE_SPEC["sha256"])' in text


def test_notebook_run_all_default_cannot_start_formal_training() -> None:
    text = _source_text()
    assert 'TRAINING_MODE = "precheck"' in text
    assert 'if TRAINING_MODE == "full" and AUTHORIZATION != "AUTHORIZE_STAIRKID_FULL_TRAINING":' in text
    assert 'raise RuntimeError("FULL_TRAINING_NOT_AUTHORIZED")' in text
