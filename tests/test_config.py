from pathlib import Path

import pytest

from stair_agent.config import AppConfig, ConfigError


def test_defaults() -> None:
    config = AppConfig.from_dict({})
    assert config.capture.target_fps == 15
    assert config.controls.input_backend == "pyautogui"
    assert config.safety.emergency_stop_key == "f8"
    assert config.safety.block_on_related_windows
    assert config.events.landing_contact_gap == 6
    assert config.events.spring_contact_gap == 12
    assert config.environment.max_episode_steps == 3000
    assert config.environment.floor_reward == 1.0
    assert config.environment.step_penalty == 0.01
    assert not config.environment.auto_restart_on_reset
    assert config.environment.reset_required_consecutive_frames == 3
    assert config.environment.max_observation_platforms == 8
    assert config.environment.observation_history_frames == 4
    assert config.environment.include_action_history
    assert config.training.algorithm == "ppo"
    assert config.training.device == "cpu"
    assert config.training.max_episodes == 3
    assert config.baseline.max_episode_steps == 300
    assert config.baseline.direction_switch_release_frames == 1


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

    with pytest.raises(ConfigError, match="include_action_history"):
        AppConfig.from_dict(
            {"environment": {"include_action_history": "yes"}}
        )

    with pytest.raises(ConfigError, match="step_penalty"):
        AppConfig.from_dict({"environment": {"step_penalty": -0.1}})


def test_invalid_baseline_config() -> None:
    with pytest.raises(ConfigError, match="horizontal_deadzone_pixels"):
        AppConfig.from_dict(
            {"baseline": {"horizontal_deadzone_pixels": -1}}
        )


def test_invalid_training_config() -> None:
    with pytest.raises(ConfigError, match="algorithm"):
        AppConfig.from_dict({"training": {"algorithm": "dqn"}})

    with pytest.raises(ConfigError, match="n_steps"):
        AppConfig.from_dict(
            {"training": {"n_steps": 63, "batch_size": 32}}
        )

    with pytest.raises(ConfigError, match="device"):
        AppConfig.from_dict({"training": {"device": "cuda"}})
