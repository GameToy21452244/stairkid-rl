from pathlib import Path

import pytest

from stair_agent.config import AppConfig, ConfigError


def test_defaults() -> None:
    config = AppConfig.from_dict({})
    assert config.capture.target_fps == 15
    assert config.controls.input_backend == "pyautogui"
    assert config.controls.menu_focus_correction_key is None
    assert config.safety.emergency_stop_key == "f8"
    assert config.safety.block_on_related_windows
    assert config.events.landing_contact_gap == 6
    assert config.events.spring_contact_gap == 12
    assert config.environment.max_episode_steps == 3000
    assert config.environment.floor_reward == 1.0
    assert config.environment.step_penalty == 0.01
    assert not config.environment.auto_restart_on_reset
    assert config.environment.reset_required_consecutive_frames == 3
    assert config.environment.reset_focus_max_observation_frames == 24
    assert config.environment.max_observation_platforms == 8
    assert config.environment.observation_history_frames == 4
    assert config.environment.include_action_history


def test_parse_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("capture:\n  target_fps: 20\n", encoding="utf-8")
    assert AppConfig.load(path).capture.target_fps == 20


def test_invalid_exe_path() -> None:
    config = AppConfig.from_dict({"game": {"exe_path": "Z:/missing/game.exe"}})
    with pytest.raises(ConfigError, match="無效"):
        config.validated_exe_path()


def test_invalid_environment_config() -> None:
    with pytest.raises(ConfigError, match="max_episode_steps"):
        AppConfig.from_dict({"environment": {"max_episode_steps": 0}})

    with pytest.raises(ConfigError, match="reset_max_observation_frames"):
        AppConfig.from_dict(
            {"environment": {"reset_max_observation_frames": 0}}
        )

    with pytest.raises(ConfigError, match="observation_history_frames"):
        AppConfig.from_dict(
            {"environment": {"observation_history_frames": 0}}
        )

    with pytest.raises(ConfigError, match="reset_focus_max"):
        AppConfig.from_dict(
            {
                "environment": {
                    "reset_focus_max_observation_frames": 2,
                }
            }
        )

    with pytest.raises(ConfigError, match="include_action_history"):
        AppConfig.from_dict(
            {"environment": {"include_action_history": "yes"}}
        )

    with pytest.raises(ConfigError, match="step_penalty"):
        AppConfig.from_dict({"environment": {"step_penalty": -0.1}})

    with pytest.raises(ConfigError, match="inner_dark_ratio"):
        AppConfig.from_dict(
            {
                "detection": {
                    "menu_focus_inner_dark_ratio_min": 1.1,
                }
            }
        )

    with pytest.raises(ConfigError, match="menu_focus_correction_key"):
        AppConfig.from_dict(
            {"controls": {"menu_focus_correction_key": ""}}
        )


def test_retired_sections_are_rejected() -> None:
    for section in ("training", "baseline", "diagnostics"):
        with pytest.raises(ConfigError, match="未知的設定區段"):
            AppConfig.from_dict({section: {}})
