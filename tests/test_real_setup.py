from __future__ import annotations

from pathlib import Path
import shutil

from stair_agent.config import AppConfig
from stair_agent.real.setup import initialize_local_config, inspect_real_setup


ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path: Path) -> Path:
    shutil.copyfile(ROOT / "config.example.yaml", tmp_path / "config.example.yaml")
    shutil.copytree(ROOT / "real_assets", tmp_path / "real_assets")
    return tmp_path


def test_first_run_initializes_standard_ns_shaft_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path, created = initialize_local_config(root)
    config = AppConfig.load(path)
    assert created is True
    assert config.game.window_title_contains == "NS-SHAFT"
    assert config.game.window_class_name == "NsShaftClass"
    assert config.capture.resize_width == 634
    assert config.capture.resize_height == 431
    assert initialize_local_config(root) == (path, False)


def test_setup_requires_local_config_and_every_declared_template(tmp_path: Path) -> None:
    root = _project(tmp_path)
    missing_config = inspect_real_setup(root)
    assert missing_config.ready is False
    assert missing_config.problems == ("REAL_CONFIG_REQUIRED",)

    report = inspect_real_setup(root, initialize=True)
    assert report.ready is True
    assert len(report.missing_templates) == 0
    assert len(report.canonical_assets_installed) == 8
    complete = inspect_real_setup(root, initialize=True)
    assert complete.ready is True
    assert complete.canonical_assets_installed == ()


def test_canonical_asset_install_is_sha_verified_and_never_overwrites_custom(tmp_path: Path) -> None:
    root = _project(tmp_path)
    custom = root / "captures/templates/dialog.png"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"custom-user-calibration")
    report = inspect_real_setup(root, initialize=True)
    assert report.ready is True
    assert custom.read_bytes() == b"custom-user-calibration"

    source = root / "real_assets/canonical_v1/templates/platform_normal.png"
    source.write_bytes(b"tampered")
    (root / "captures/templates/platform_normal.png").unlink()
    import pytest

    with pytest.raises(RuntimeError, match="CANONICAL_REAL_ASSET_SHA_MISMATCH"):
        inspect_real_setup(root, initialize=True)


def test_real_cmds_are_repo_relative_and_setup_never_runs_real_control() -> None:
    setup = (ROOT / "FIRST_RUN_SETUP.cmd").read_text(encoding="utf-8-sig").casefold()
    calibrate = (ROOT / "CALIBRATE_REAL_GAME.cmd").read_text(
        encoding="utf-8-sig"
    ).casefold()
    assert "%~dp0" in setup and ".venv\\scripts\\python.exe" in setup
    assert "pip install --upgrade pip setuptools wheel" in setup
    assert 'pip install --no-build-isolation -e ".[rl]"' in setup
    assert "run_real_agent" not in setup
    assert "bulk_real_evaluation" not in setup
    assert "%~dp0" in calibrate
    assert "stair_agent.real.calibration" in calibrate


def test_calibration_module_has_no_input_controller_or_policy_action() -> None:
    source = (ROOT / "src/stair_agent/real/calibration.py").read_text(
        encoding="utf-8"
    ).casefold()
    assert "inputcontroller" not in source
    assert ".apply(" not in source
    assert ".learn(" not in source
