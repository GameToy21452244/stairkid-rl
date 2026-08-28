from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np

from stair_agent.config import AppConfig
from stair_agent.diagnostics import load_image
from stair_agent.dialog_handler import DialogFocusLocation
from stair_agent.live_env import build_dialog_focus_guard
from stair_agent.real.setup import (
    CANONICAL_REAL_PROFILE_SHA256,
    apply_canonical_menu_profile,
    initialize_local_config,
    inspect_real_setup,
)


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
    assert config.detection.menu_start_button_left == 381
    assert config.detection.menu_two_player_button_left == 289
    assert config.detection.menu_exit_button_left == 172
    assert config.environment.auto_restart_on_reset is True
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


def test_legacy_all_null_menu_profile_is_migrated_but_partial_custom_is_not(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    config_path, _ = initialize_local_config(root)
    config = AppConfig.load(config_path)
    for name in (
        "menu_start_button_left",
        "menu_start_button_top",
        "menu_start_button_width",
        "menu_start_button_height",
        "menu_two_player_button_left",
        "menu_two_player_button_top",
        "menu_two_player_button_width",
        "menu_two_player_button_height",
        "menu_exit_button_left",
        "menu_exit_button_top",
        "menu_exit_button_width",
        "menu_exit_button_height",
    ):
        setattr(config.detection, name, None)
    config.environment.auto_restart_on_reset = False
    config.vision.flipping_platform_template_paths = [
        "captures/templates/platform_flipping_1.png",
        "captures/templates/platform_flipping_2.png",
    ]
    config.save(config_path)
    assert apply_canonical_menu_profile(config_path) is True
    migrated = AppConfig.load(config_path)
    assert migrated.detection.menu_start_button_left == 381
    assert migrated.detection.menu_two_player_button_left == 289
    assert migrated.detection.menu_exit_button_left == 172
    assert migrated.controls.menu_focus_correction_key == "tab"
    assert migrated.environment.auto_restart_on_reset is True
    assert migrated.vision.flipping_platform_template_paths == [
        "captures/templates/platform_flipping_1.png"
    ]

    migrated.detection.menu_start_button_left = 400
    migrated.detection.menu_start_button_top = None
    migrated.save(config_path)
    assert apply_canonical_menu_profile(config_path) is False
    assert AppConfig.load(config_path).detection.menu_start_button_left == 400


def test_canonical_dialog_template_confirms_historical_start_focus() -> None:
    config = AppConfig.load(ROOT / "config.example.yaml")
    template = load_image(ROOT / "real_assets/canonical_v1/templates/dialog.png")
    frame = np.zeros((431, 634, 3), dtype=np.uint8)
    frame[97 : 97 + template.shape[0], 158 : 158 + template.shape[1]] = template
    guard = build_dialog_focus_guard(config.detection)
    assert guard.focus_location(frame) is DialogFocusLocation.START
    assert CANONICAL_REAL_PROFILE_SHA256 == (
        "505187ab25459608f7f7aaa240c738dd96ccd6c745dd37f50426ff6cad91a4b6"
    )


def test_canonical_runtime_excludes_false_positive_second_flipping_crop() -> None:
    config = AppConfig.load(ROOT / "config.example.yaml")
    assert config.vision.flipping_platform_template_paths == [
        "captures/templates/platform_flipping_1.png"
    ]
    manifest = json.loads(
        (ROOT / "real_assets/canonical_v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    selection = manifest["runtime_selection"]
    assert selection["active_flipping_templates"] == ["platform_flipping_1.png"]
    assert selection["retained_inactive_templates"] == [
        "platform_flipping_2.png"
    ]
    assert selection["real_actions_sent"] == 0


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
    launcher = (ROOT / "START_REAL_MODEL_TEST.cmd").read_text(
        encoding="utf-8-sig"
    ).casefold()
    assert "--initialize --check" in launcher


def test_calibration_module_has_no_input_controller_or_policy_action() -> None:
    source = (ROOT / "src/stair_agent/real/calibration.py").read_text(
        encoding="utf-8"
    ).casefold()
    assert "inputcontroller" not in source
    assert ".apply(" not in source
    assert ".learn(" not in source
