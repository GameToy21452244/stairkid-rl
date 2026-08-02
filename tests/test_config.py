from pathlib import Path

import pytest

from stair_agent.config import AppConfig, ConfigError


def test_defaults() -> None:
    config = AppConfig.from_dict({})
    assert config.capture.target_fps == 15
    assert config.controls.input_backend == "pyautogui"
    assert config.controls.menu_focus_correction_key is None
    assert config.controls.max_continuous_hold_ms == 500
    assert config.safety.emergency_stop_key == "f8"
    assert config.safety.block_on_related_windows
    assert config.events.landing_contact_gap == 6
    assert config.events.spring_contact_gap == 12
    assert config.hud.floor_counter_left is None
    assert config.hud.floor_counter_initial_value == 1
    assert config.hud.floor_change_required_consecutive == 2
    assert config.environment.max_episode_steps == 3000
    assert config.environment.floor_reward == 1.0
    assert config.environment.step_penalty == 0.01
    assert config.environment.direction_change_penalty == 0.02
    assert config.environment.direction_change_window_steps == 2
    assert config.environment.spike_dwell_penalty == 0.03
    assert config.environment.spike_dwell_grace_steps == 2
    assert config.environment.spike_contact_max_gap == 12
    assert config.environment.idle_action_penalty == 0.02
    assert config.environment.idle_action_grace_steps == 2
    assert config.environment.platform_dwell_penalty == 0.02
    assert config.environment.platform_dwell_grace_steps == 12
    assert config.environment.platform_dwell_max_gap == 80
    assert config.environment.top_danger_penalty == 0.03
    assert config.environment.top_danger_grace_steps == 2
    assert config.environment.top_danger_y_ratio == 0.33
    assert config.environment.wall_margin_pixels == 32
    assert config.environment.wall_push_penalty == 0.08
    assert config.environment.platform_alignment_reward_scale == 0.5
    assert config.environment.platform_target_action_reward == 0.05
    assert (
        config.environment.platform_alignment_rising_origin_exclusion_gap
        == 150
    )
    assert config.environment.platform_alignment_safe_kinds == [
        "normal",
        "spring",
        "conveyor",
        "flipping",
    ]
    assert not config.environment.auto_restart_on_reset
    assert config.environment.reset_required_consecutive_frames == 3
    assert config.environment.reset_focus_max_observation_frames == 24
    assert (
        config.environment.reset_focus_correction_max_observation_frames
        == 12
    )
    assert config.environment.reset_focus_correction_max_presses == 3
    assert config.environment.max_observation_platforms == 8
    assert config.environment.observation_history_frames == 4
    assert config.environment.include_action_history
    assert config.training.algorithm == "ppo"
    assert config.training.device == "cpu"
    assert config.training.max_episodes == 3
    assert config.training.n_epochs == 4
    assert config.training.learning_rate == 0.0002
    assert config.training.ent_coef == 0.03
    assert config.training.target_kl == 0.01
    assert config.training.seed == 2
    assert config.baseline.max_episode_steps == 300
    assert config.baseline.direction_switch_release_frames == 1
    assert config.baseline.recovery_full_health_segments == 12


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

    with pytest.raises(ConfigError, match="reset_focus_correction_max"):
        AppConfig.from_dict(
            {
                "environment": {
                    "reset_focus_correction_max_observation_frames": 2,
                }
            }
        )

    with pytest.raises(ConfigError, match="include_action_history"):
        AppConfig.from_dict(
            {"environment": {"include_action_history": "yes"}}
        )

    with pytest.raises(ConfigError, match="step_penalty"):
        AppConfig.from_dict({"environment": {"step_penalty": -0.1}})

    with pytest.raises(ConfigError, match="direction_change_window_steps"):
        AppConfig.from_dict(
            {"environment": {"direction_change_window_steps": -1}}
        )

    with pytest.raises(ConfigError, match="spike_dwell_grace_steps"):
        AppConfig.from_dict(
            {"environment": {"spike_dwell_grace_steps": -1}}
        )

    with pytest.raises(ConfigError, match="idle_action_grace_steps"):
        AppConfig.from_dict(
            {"environment": {"idle_action_grace_steps": -1}}
        )

    with pytest.raises(ConfigError, match="platform_dwell_grace_steps"):
        AppConfig.from_dict(
            {"environment": {"platform_dwell_grace_steps": -1}}
        )

    with pytest.raises(ConfigError, match="top_danger_y_ratio"):
        AppConfig.from_dict(
            {"environment": {"top_danger_y_ratio": 1.1}}
        )

    with pytest.raises(ConfigError, match="wall_margin_pixels"):
        AppConfig.from_dict(
            {"environment": {"wall_margin_pixels": -1}}
        )

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

    with pytest.raises(ConfigError, match=r"floor_counter_\*"):
        AppConfig.from_dict({"hud": {"floor_counter_left": 10}})

    with pytest.raises(ConfigError, match="stability/change"):
        AppConfig.from_dict(
            {
                "hud": {
                    "floor_stability_ratio_threshold": 0.05,
                    "floor_change_ratio_threshold": 0.04,
                }
            }
        )

    with pytest.raises(ConfigError, match="max_continuous_hold_ms"):
        AppConfig.from_dict(
            {
                "controls": {
                    "action_duration_ms": 80,
                    "max_continuous_hold_ms": 40,
                }
            }
        )


def test_invalid_baseline_config() -> None:
    with pytest.raises(ConfigError, match="horizontal_deadzone_pixels"):
        AppConfig.from_dict(
            {"baseline": {"horizontal_deadzone_pixels": -1}}
        )

    with pytest.raises(ConfigError, match="special_contact_escape_max_steps"):
        AppConfig.from_dict(
            {"baseline": {"special_contact_escape_max_steps": 0}}
        )

    with pytest.raises(ConfigError, match="aligned_platform_dwell_escape_steps"):
        AppConfig.from_dict(
            {"baseline": {"aligned_platform_dwell_escape_steps": 0}}
        )

    with pytest.raises(ConfigError, match="top_pressure_memory_steps"):
        AppConfig.from_dict(
            {"baseline": {"top_pressure_memory_steps": 0}}
        )

    with pytest.raises(ConfigError, match="top_pressure_dropout_continue_steps"):
        AppConfig.from_dict(
            {
                "baseline": {
                    "top_pressure_memory_steps": 2,
                    "top_pressure_dropout_continue_steps": 3,
                }
            }
        )

    with pytest.raises(ConfigError, match="support_departure_abort_cooldown_steps"):
        AppConfig.from_dict(
            {"baseline": {"support_departure_abort_cooldown_steps": 0}}
        )

    with pytest.raises(ConfigError, match="landing_prediction_max_seconds"):
        AppConfig.from_dict(
            {
                "baseline": {
                    "landing_velocity_lookahead_seconds": 0.4,
                    "landing_prediction_max_seconds": 0.3,
                }
            }
        )

    with pytest.raises(
        ConfigError,
        match="landing_release_projection_seconds",
    ):
        AppConfig.from_dict(
            {
                "baseline": {
                    "landing_prediction_max_seconds": 0.4,
                    "landing_release_projection_seconds": 0.5,
                }
            }
        )

    with pytest.raises(
        ConfigError,
        match="landing_vertical_speed_floor_pixels_per_second",
    ):
        AppConfig.from_dict(
            {
                "baseline": {
                    "landing_vertical_speed_floor_pixels_per_second": 0,
                }
            }
        )

    with pytest.raises(ConfigError, match="playfield_right_pixels"):
        AppConfig.from_dict(
            {
                "baseline": {
                    "playfield_left_pixels": 100,
                    "playfield_right_pixels": 100,
                }
            }
        )

    with pytest.raises(ConfigError, match="wall_guard_margin_pixels"):
        AppConfig.from_dict(
            {"baseline": {"wall_guard_margin_pixels": 999}}
        )

    with pytest.raises(ConfigError, match="wall_evacuation_exit_margin_pixels"):
        AppConfig.from_dict(
            {
                "baseline": {
                    "wall_guard_margin_pixels": 32,
                    "wall_evacuation_exit_margin_pixels": 20,
                }
            }
        )

    with pytest.raises(ConfigError, match="launch_commit_max_steps"):
        AppConfig.from_dict(
            {"baseline": {"launch_commit_max_steps": 0}}
        )

    with pytest.raises(ConfigError, match="support_departure_max_steps"):
        AppConfig.from_dict(
            {"baseline": {"support_departure_max_steps": 0}}
        )
    with pytest.raises(ConfigError, match="support_departure_lost_frames"):
        AppConfig.from_dict(
            {"baseline": {"support_departure_lost_frames": 0}}
        )


def test_invalid_player_continuity_config() -> None:
    with pytest.raises(ConfigError, match="player_close_kernel_size"):
        AppConfig.from_dict(
            {"vision": {"player_close_kernel_size": 0}}
        )

    with pytest.raises(ConfigError, match="player_min_colored_pixels"):
        AppConfig.from_dict(
            {"vision": {"player_min_colored_pixels": 0}}
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
