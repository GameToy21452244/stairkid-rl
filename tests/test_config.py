from pathlib import Path

import pytest

from stair_agent.config import AppConfig, ConfigError


def test_defaults() -> None:
    config = AppConfig.from_dict({})
    assert config.capture.target_fps == 15
    assert config.controls.input_backend == "pyautogui"
    assert config.safety.emergency_stop_key == "f8"


def test_parse_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("capture:\n  target_fps: 20\n", encoding="utf-8")
    assert AppConfig.load(path).capture.target_fps == 20


def test_invalid_exe_path() -> None:
    config = AppConfig.from_dict({"game": {"exe_path": "Z:/missing/game.exe"}})
    with pytest.raises(ConfigError, match="無效"):
        config.validated_exe_path()
