from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """設定內容無效。"""


@dataclass
class GameConfig:
    exe_path: str = "請使用者填入完整 exe 路徑"
    window_title_contains: str = "請使用者填入部分視窗標題"
    window_class_name: str | None = None
    auto_launch: bool = False
    launch_wait_seconds: float = 3.0


@dataclass
class CaptureConfig:
    mode: str = "client_area"
    left: int | None = None
    top: int | None = None
    width: int | None = None
    height: int | None = None
    target_fps: int = 15
    resize_width: int = 320
    resize_height: int = 480
    grayscale: bool = False


@dataclass
class ControlsConfig:
    left_key: str = "left"
    right_key: str = "right"
    restart_key: str = "enter"
    pause_key: str | None = None
    action_duration_ms: int = 80
    max_continuous_hold_ms: int = 500
    restart_duration_ms: int = 200
    menu_focus_correction_key: str | None = None
    input_backend: str = "pyautogui"


@dataclass
class SafetyConfig:
    emergency_stop_key: str = "f8"
    require_foreground_window: bool = True
    release_keys_on_error: bool = True
    block_on_related_windows: bool = True


@dataclass
class DiagnosticsConfig:
    save_debug_frames: bool = True
    show_fps: bool = True
    draw_capture_border: bool = True


@dataclass
class DetectionConfig:
    dialog_template_path: str = "captures/templates/dialog.png"
    dialog_roi_left: int | None = None
    dialog_roi_top: int | None = None
    dialog_roi_width: int | None = None
    dialog_roi_height: int | None = None
    reference_width: int | None = None
    reference_height: int | None = None
    dialog_threshold: float = 0.80
    search_margin: int = 8
    menu_start_button_left: int | None = None
    menu_start_button_top: int | None = None
    menu_start_button_width: int | None = None
    menu_start_button_height: int | None = None
    menu_two_player_button_left: int | None = None
    menu_two_player_button_top: int | None = None
    menu_two_player_button_width: int | None = None
    menu_two_player_button_height: int | None = None
    menu_exit_button_left: int | None = None
    menu_exit_button_top: int | None = None
    menu_exit_button_width: int | None = None
    menu_exit_button_height: int | None = None
    menu_focus_border_mean_max: float = 180.0
    menu_focus_minimum_contrast: float = 20.0
    menu_focus_inner_gray_max: int = 80
    menu_focus_inner_dark_ratio_min: float = 0.20


@dataclass
class VisionConfig:
    playfield_left: int | None = None
    playfield_top: int | None = None
    playfield_width: int | None = None
    playfield_height: int | None = None
    reference_width: int | None = None
    reference_height: int | None = None
    player_hue_max: int = 40
    player_saturation_min: int = 140
    player_value_min: int = 170
    player_min_width: int = 15
    player_max_width: int = 50
    player_min_height: int = 14
    player_max_height: int = 50
    player_dilate_width: int = 7
    player_dilate_height: int = 9
    player_close_kernel_size: int = 3
    player_min_colored_pixels: int = 12
    normal_platform_template_path: str = "captures/templates/platform_normal.png"
    normal_platform_threshold: float = 0.90
    spikes_platform_template_path: str = "captures/templates/platform_spikes.png"
    spikes_platform_threshold: float = 0.90
    green_platform_template_path: str = "captures/templates/platform_green.png"
    green_platform_template_paths: list[str] = field(default_factory=list)
    green_platform_threshold: float = 0.90
    metal_platform_template_path: str = "captures/templates/platform_metal.png"
    metal_platform_template_paths: list[str] = field(default_factory=list)
    metal_platform_threshold: float = 0.90
    flipping_platform_template_paths: list[str] = field(default_factory=list)
    flipping_platform_threshold: float = 0.90
    platform_match_blur_kernel_size: int = 9
    platform_match_blur_kinds: list[str] = field(
        default_factory=lambda: [
            "normal",
            "spikes",
            "spring",
            "conveyor",
            "unknown",
        ]
    )


@dataclass
class HudConfig:
    reference_width: int | None = None
    reference_height: int | None = None
    life_left: int | None = None
    life_top: int | None = None
    life_segment_width: int = 6
    life_segment_height: int = 14
    life_segment_pitch: int = 8
    life_max_segments: int = 12
    life_red_min: int = 170
    life_green_min: int = 100
    life_blue_max: int = 100
    life_filled_ratio: float = 0.50
    floor_counter_left: int | None = None
    floor_counter_top: int | None = None
    floor_counter_width: int | None = None
    floor_counter_height: int | None = None
    floor_counter_initial_value: int = 1
    floor_binary_threshold: int = 120
    floor_change_ratio_threshold: float = 0.025
    floor_stability_ratio_threshold: float = 0.02
    floor_change_required_consecutive: int = 2


@dataclass
class EventsConfig:
    landing_contact_gap: int = 6
    spring_contact_gap: int = 12
    correlation_frames: int = 5


@dataclass
class EnvironmentConfig:
    max_episode_steps: int = 3000
    floor_reward: float = 1.0
    step_penalty: float = 0.01
    direction_change_penalty: float = 0.02
    direction_change_window_steps: int = 2
    spike_dwell_penalty: float = 0.03
    spike_dwell_grace_steps: int = 2
    spike_contact_max_gap: int = 12
    idle_action_penalty: float = 0.02
    idle_action_grace_steps: int = 2
    platform_dwell_penalty: float = 0.02
    platform_dwell_grace_steps: int = 12
    platform_dwell_max_gap: int = 80
    top_danger_penalty: float = 0.03
    top_danger_grace_steps: int = 2
    top_danger_y_ratio: float = 0.33
    wall_margin_pixels: int = 32
    wall_push_penalty: float = 0.08
    platform_alignment_reward_scale: float = 0.5
    platform_target_action_reward: float = 0.05
    platform_alignment_min_vertical_gap: int = 25
    platform_alignment_max_vertical_gap: int = 260
    platform_alignment_landing_margin: int = 10
    platform_alignment_rising_origin_exclusion_gap: int = 150
    platform_alignment_safe_kinds: list[str] = field(
        default_factory=lambda: [
            "normal",
            "spring",
            "conveyor",
            "flipping",
        ]
    )
    damage_penalty_per_segment: float = 0.2
    death_penalty: float = 5.0
    velocity_scale: float = 500.0
    max_platforms_per_type: int = 8
    auto_restart_on_reset: bool = False
    reset_required_consecutive_frames: int = 3
    reset_max_observation_frames: int = 30
    reset_focus_max_observation_frames: int = 24
    reset_focus_correction_max_observation_frames: int = 12
    reset_focus_correction_max_presses: int = 3
    reset_post_action_delay_seconds: float = 0.4
    max_observation_platforms: int = 8
    observation_history_frames: int = 4
    include_action_history: bool = True


@dataclass
class TrainingConfig:
    algorithm: str = "ppo"
    total_timesteps: int = 1024
    max_episodes: int = 3
    max_training_seconds: float = 120.0
    n_steps: int = 128
    batch_size: int = 64
    n_epochs: int = 4
    learning_rate: float = 0.0002
    gamma: float = 0.99
    gae_lambda: float = 0.95
    ent_coef: float = 0.03
    target_kl: float = 0.01
    seed: int = 2
    device: str = "cpu"
    checkpoint_freq_steps: int = 256
    model_dir: str = "models/ppo"
    policy_hidden_sizes: list[int] = field(
        default_factory=lambda: [128, 128]
    )


@dataclass
class BaselineConfig:
    max_episode_steps: int = 300
    max_episode_seconds: float = 30.0
    horizontal_deadzone_pixels: float = 12.0
    min_target_vertical_gap_pixels: float = 25.0
    max_target_vertical_gap_pixels: float = 260.0
    hazard_vertical_gap_pixels: float = 180.0
    hazard_horizontal_margin_pixels: float = 64.0
    direction_switch_release_frames: int = 1
    rising_origin_exclusion_gap_pixels: float = 150.0
    rising_origin_horizontal_margin_pixels: float = 12.0
    target_reacquire_distance_pixels: float = 80.0
    landing_margin_pixels: float = 10.0
    reachability_base_pixels: float = 70.0
    reachability_per_vertical_pixel: float = 0.8
    launch_platform_vertical_gap_pixels: float = 30.0
    launch_escape_clearance_pixels: float = 16.0
    launch_commit_max_steps: int = 3
    launch_replan_cooldown_steps: int = 2
    support_departure_max_steps: int = 8
    support_departure_lost_frames: int = 1
    support_departure_abort_cooldown_steps: int = 2
    post_launch_coast_frames: int = 2
    landing_velocity_lookahead_seconds: float = 0.25
    landing_prediction_max_seconds: float = 0.55
    landing_release_projection_seconds: float = 0.05
    landing_vertical_speed_floor_pixels_per_second: float = 80.0
    special_escape_edge_guard_pixels: float = 12.0
    special_escape_outward_velocity_threshold_pixels_per_second: float = 40.0
    special_contact_direction_commit_steps: int = 3
    special_contact_destination_stability_steps: int = 2
    special_contact_replan_limit: int = 1
    special_contact_forced_exit_steps: int = 4
    special_contact_reacquire_center_tolerance_pixels: float = 32.0
    fallback_center_x_pixels: float = 231.5
    top_danger_player_y_threshold: float = 140.0
    top_pressure_memory_steps: int = 4
    top_pressure_dropout_continue_steps: int = 2
    top_pressure_support_settle_steps: int = 2
    deep_landing_horizontal_cost: float = 0.75
    emergency_spike_min_health_segments: int = 6
    recovery_full_health_segments: int = 12
    special_contact_escape_max_steps: int = 12
    aligned_platform_dwell_escape_steps: int = 4
    aligned_platform_dwell_gap_tolerance_pixels: float = 3.0
    playfield_left_pixels: float = 40.0
    playfield_right_pixels: float = 423.0
    wall_guard_margin_pixels: float = 32.0
    wall_guard_velocity_lookahead_seconds: float = 0.20
    wall_evacuation_exit_margin_pixels: float = 64.0
    wall_evacuation_cooldown_steps: int = 4
    safe_platform_kinds: list[str] = field(
        default_factory=lambda: [
            "normal",
            "spring",
            "conveyor",
            "flipping",
        ]
    )


@dataclass
class AppConfig:
    game: GameConfig = field(default_factory=GameConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    controls: ControlsConfig = field(default_factory=ControlsConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    hud: HudConfig = field(default_factory=HudConfig)
    events: EventsConfig = field(default_factory=EventsConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    baseline: BaselineConfig = field(default_factory=BaselineConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppConfig":
        data = data or {}
        known = {
            "game",
            "capture",
            "controls",
            "safety",
            "diagnostics",
            "detection",
            "vision",
            "hud",
            "events",
            "environment",
            "training",
            "baseline",
        }
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"未知的設定區段：{', '.join(sorted(unknown))}")
        config = cls(
            game=GameConfig(**data.get("game", {})),
            capture=CaptureConfig(**data.get("capture", {})),
            controls=ControlsConfig(**data.get("controls", {})),
            safety=SafetyConfig(**data.get("safety", {})),
            diagnostics=DiagnosticsConfig(**data.get("diagnostics", {})),
            detection=DetectionConfig(**data.get("detection", {})),
            vision=VisionConfig(**data.get("vision", {})),
            hud=HudConfig(**data.get("hud", {})),
            events=EventsConfig(**data.get("events", {})),
            environment=EnvironmentConfig(**data.get("environment", {})),
            training=TrainingConfig(**data.get("training", {})),
            baseline=BaselineConfig(**data.get("baseline", {})),
        )
        config.validate()
        return config

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.is_file():
            raise ConfigError(
                f"找不到設定檔：{config_path}。請先複製 config.example.yaml 為 config.yaml。"
            )
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML 格式錯誤：{exc}") from exc
        if raw is not None and not isinstance(raw, dict):
            raise ConfigError("設定檔最外層必須是 YAML mapping。")
        try:
            return cls.from_dict(raw)
        except TypeError as exc:
            raise ConfigError(f"設定欄位或型別無效：{exc}") from exc

    def validate(self) -> None:
        if self.capture.mode not in {"client_area", "manual"}:
            raise ConfigError("capture.mode 必須是 client_area 或 manual。")
        if self.capture.target_fps <= 0:
            raise ConfigError("capture.target_fps 必須大於 0。")
        for name in ("resize_width", "resize_height"):
            value = getattr(self.capture, name)
            if value is not None and value <= 0:
                raise ConfigError(f"capture.{name} 必須大於 0。")
        if self.controls.input_backend not in {"pyautogui", "pydirectinput"}:
            raise ConfigError("controls.input_backend 必須是 pyautogui 或 pydirectinput。")
        if self.controls.action_duration_ms <= 0:
            raise ConfigError("controls.action_duration_ms 必須大於 0。")
        if (
            self.controls.max_continuous_hold_ms
            < self.controls.action_duration_ms
        ):
            raise ConfigError(
                "controls.max_continuous_hold_ms 不可小於 action_duration_ms。"
            )
        if self.controls.restart_duration_ms <= 0:
            raise ConfigError("controls.restart_duration_ms 必須大於 0。")
        if (
            self.controls.menu_focus_correction_key is not None
            and not self.controls.menu_focus_correction_key.strip()
        ):
            raise ConfigError(
                "controls.menu_focus_correction_key 必須是非空字串或 null。"
            )
        if not 0.0 < self.detection.dialog_threshold <= 1.0:
            raise ConfigError("detection.dialog_threshold 必須介於 0 與 1 之間。")
        if self.detection.search_margin < 0:
            raise ConfigError("detection.search_margin 不可小於 0。")
        if not 0 <= self.detection.menu_focus_border_mean_max <= 255:
            raise ConfigError(
                "detection.menu_focus_border_mean_max 必須介於 0 與 255。"
            )
        if self.detection.menu_focus_minimum_contrast < 0:
            raise ConfigError(
                "detection.menu_focus_minimum_contrast 不可小於 0。"
            )
        if not 0 <= self.detection.menu_focus_inner_gray_max <= 255:
            raise ConfigError(
                "detection.menu_focus_inner_gray_max 必須介於 0 與 255。"
            )
        if not (
            0.0
            <= self.detection.menu_focus_inner_dark_ratio_min
            <= 1.0
        ):
            raise ConfigError(
                "detection.menu_focus_inner_dark_ratio_min "
                "必須介於 0 與 1。"
            )
        if not 0.0 < self.vision.normal_platform_threshold <= 1.0:
            raise ConfigError("vision.normal_platform_threshold 必須介於 0 與 1。")
        for name in (
            "spikes_platform_threshold",
            "green_platform_threshold",
            "metal_platform_threshold",
            "flipping_platform_threshold",
        ):
            value = getattr(self.vision, name)
            if not 0.0 < value <= 1.0:
                raise ConfigError(f"vision.{name} 必須介於 0 與 1。")
        blur_kernel = int(self.vision.platform_match_blur_kernel_size)
        if blur_kernel <= 0 or blur_kernel % 2 == 0:
            raise ConfigError(
                "vision.platform_match_blur_kernel_size 必須是正奇數。"
            )
        blur_kinds = self.vision.platform_match_blur_kinds
        known_blur_kinds = {
            "normal",
            "spikes",
            "spring",
            "conveyor",
            "flipping",
            "unknown",
        }
        if (
            not isinstance(blur_kinds, list)
            or len(set(blur_kinds)) != len(blur_kinds)
            or any(kind not in known_blur_kinds for kind in blur_kinds)
        ):
            raise ConfigError(
                "vision.platform_match_blur_kinds 必須是不重複的已知平台類型清單。"
            )
        for name in (
            "metal_platform_template_paths",
            "green_platform_template_paths",
            "flipping_platform_template_paths",
        ):
            values = getattr(self.vision, name)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ConfigError(f"vision.{name} 必須是非空字串清單。")
        if self.vision.player_dilate_width <= 0 or self.vision.player_dilate_height <= 0:
            raise ConfigError("vision.player_dilate_width/height 必須大於 0。")
        if self.vision.player_close_kernel_size <= 0:
            raise ConfigError("vision.player_close_kernel_size 必須大於 0。")
        if self.vision.player_min_colored_pixels <= 0:
            raise ConfigError("vision.player_min_colored_pixels 必須大於 0。")
        for name in (
            "life_segment_width",
            "life_segment_height",
            "life_segment_pitch",
            "life_max_segments",
        ):
            if getattr(self.hud, name) <= 0:
                raise ConfigError(f"hud.{name} 必須大於 0。")
        if not 0.0 < self.hud.life_filled_ratio <= 1.0:
            raise ConfigError("hud.life_filled_ratio 必須介於 0 與 1。")
        for name in ("life_red_min", "life_green_min", "life_blue_max"):
            if not 0 <= getattr(self.hud, name) <= 255:
                raise ConfigError(f"hud.{name} 必須介於 0 與 255。")
        floor_roi = (
            self.hud.floor_counter_left,
            self.hud.floor_counter_top,
            self.hud.floor_counter_width,
            self.hud.floor_counter_height,
        )
        if any(value is not None for value in floor_roi):
            if any(value is None for value in floor_roi):
                raise ConfigError("hud.floor_counter_* 必須全部設定或全部為 null。")
            if any(int(value) < 0 for value in floor_roi[:2]):
                raise ConfigError("hud.floor_counter_left/top 不可小於 0。")
            if any(int(value) <= 0 for value in floor_roi[2:]):
                raise ConfigError("hud.floor_counter_width/height 必須大於 0。")
        if self.hud.floor_counter_initial_value < 0:
            raise ConfigError("hud.floor_counter_initial_value 不可小於 0。")
        if not 0 <= self.hud.floor_binary_threshold <= 255:
            raise ConfigError("hud.floor_binary_threshold 必須介於 0 與 255。")
        if not (
            0.0 <= self.hud.floor_stability_ratio_threshold
            < self.hud.floor_change_ratio_threshold
            <= 1.0
        ):
            raise ConfigError(
                "hud floor stability/change threshold 必須滿足 0 <= stability < change <= 1。"
            )
        if self.hud.floor_change_required_consecutive <= 0:
            raise ConfigError(
                "hud.floor_change_required_consecutive 必須大於 0。"
            )
        for name in (
            "landing_contact_gap",
            "spring_contact_gap",
            "correlation_frames",
        ):
            if getattr(self.events, name) <= 0:
                raise ConfigError(f"events.{name} 必須大於 0。")
        for name in (
            "max_episode_steps",
            "velocity_scale",
            "max_platforms_per_type",
            "reset_required_consecutive_frames",
            "reset_max_observation_frames",
            "reset_focus_max_observation_frames",
            "reset_focus_correction_max_observation_frames",
            "reset_focus_correction_max_presses",
            "max_observation_platforms",
            "observation_history_frames",
        ):
            if getattr(self.environment, name) <= 0:
                raise ConfigError(f"environment.{name} 必須大於 0。")
        if not isinstance(self.environment.include_action_history, bool):
            raise ConfigError(
                "environment.include_action_history 必須是布林值。"
            )
        if (
            self.environment.reset_max_observation_frames
            < self.environment.reset_required_consecutive_frames
        ):
            raise ConfigError(
                "environment.reset_max_observation_frames 不可小於"
                " reset_required_consecutive_frames。"
            )
        if (
            self.environment.reset_focus_max_observation_frames
            < self.environment.reset_required_consecutive_frames
        ):
            raise ConfigError(
                "environment.reset_focus_max_observation_frames 不可小於"
                " reset_required_consecutive_frames。"
            )
        if (
            self.environment.reset_focus_correction_max_observation_frames
            < self.environment.reset_required_consecutive_frames
        ):
            raise ConfigError(
                "environment.reset_focus_correction_max_observation_frames "
                "不可小於 reset_required_consecutive_frames。"
            )
        if self.environment.reset_focus_correction_max_presses > 4:
            raise ConfigError(
                "environment.reset_focus_correction_max_presses "
                "不可大於 4。"
            )
        for name in (
            "floor_reward",
            "step_penalty",
            "direction_change_penalty",
            "spike_dwell_penalty",
            "idle_action_penalty",
            "platform_dwell_penalty",
            "top_danger_penalty",
            "wall_push_penalty",
            "platform_alignment_reward_scale",
            "platform_target_action_reward",
            "damage_penalty_per_segment",
            "death_penalty",
            "reset_post_action_delay_seconds",
        ):
            if getattr(self.environment, name) < 0:
                raise ConfigError(f"environment.{name} 不可小於 0。")
        for name in (
            "direction_change_window_steps",
            "spike_dwell_grace_steps",
            "spike_contact_max_gap",
            "idle_action_grace_steps",
            "platform_dwell_grace_steps",
            "platform_dwell_max_gap",
            "top_danger_grace_steps",
            "wall_margin_pixels",
            "platform_alignment_min_vertical_gap",
            "platform_alignment_max_vertical_gap",
            "platform_alignment_landing_margin",
            "platform_alignment_rising_origin_exclusion_gap",
        ):
            if getattr(self.environment, name) < 0:
                raise ConfigError(f"environment.{name} 不可小於 0。")
        if not 0.0 <= self.environment.top_danger_y_ratio <= 1.0:
            raise ConfigError(
                "environment.top_danger_y_ratio 必須介於 0 與 1。"
            )
        if (
            self.environment.platform_alignment_max_vertical_gap
            < self.environment.platform_alignment_min_vertical_gap
        ):
            raise ConfigError(
                "environment.platform_alignment_max_vertical_gap "
                "不可小於 platform_alignment_min_vertical_gap。"
            )
        known_platform_kinds = {
            "normal",
            "spikes",
            "spring",
            "conveyor",
            "flipping",
        }
        if (
            not self.environment.platform_alignment_safe_kinds
            or any(
                kind not in known_platform_kinds
                for kind in self.environment.platform_alignment_safe_kinds
            )
        ):
            raise ConfigError(
                "environment.platform_alignment_safe_kinds "
                "必須是已知平台類型的非空清單。"
            )
        if self.training.algorithm != "ppo":
            raise ConfigError("training.algorithm 目前只支援 ppo。")
        if self.training.device != "cpu":
            raise ConfigError("training.device 本階段只允許 cpu。")
        for name in (
            "total_timesteps",
            "max_episodes",
            "n_steps",
            "batch_size",
            "n_epochs",
            "checkpoint_freq_steps",
        ):
            if getattr(self.training, name) <= 0:
                raise ConfigError(f"training.{name} 必須大於 0。")
        if self.training.max_training_seconds <= 0:
            raise ConfigError(
                "training.max_training_seconds 必須大於 0。"
            )
        if self.training.n_steps % self.training.batch_size != 0:
            raise ConfigError(
                "training.n_steps 必須可被 batch_size 整除。"
            )
        for name in (
            "learning_rate",
            "gamma",
            "gae_lambda",
            "target_kl",
        ):
            value = getattr(self.training, name)
            if not 0.0 < value <= 1.0:
                raise ConfigError(f"training.{name} 必須介於 0 與 1。")
        if self.training.ent_coef < 0:
            raise ConfigError("training.ent_coef 不可小於 0。")
        if (
            not isinstance(self.training.model_dir, str)
            or not self.training.model_dir.strip()
        ):
            raise ConfigError("training.model_dir 不可為空。")
        if (
            not isinstance(self.training.policy_hidden_sizes, list)
            or not self.training.policy_hidden_sizes
            or not all(
                isinstance(size, int) and size > 0
                for size in self.training.policy_hidden_sizes
            )
        ):
            raise ConfigError(
                "training.policy_hidden_sizes 必須是正整數清單。"
            )
        for name in ("max_episode_steps", "max_episode_seconds"):
            if getattr(self.baseline, name) <= 0:
                raise ConfigError(f"baseline.{name} 必須大於 0。")
        for name in (
            "horizontal_deadzone_pixels",
            "min_target_vertical_gap_pixels",
            "max_target_vertical_gap_pixels",
            "hazard_vertical_gap_pixels",
            "hazard_horizontal_margin_pixels",
            "rising_origin_exclusion_gap_pixels",
            "rising_origin_horizontal_margin_pixels",
            "target_reacquire_distance_pixels",
            "landing_margin_pixels",
            "reachability_base_pixels",
            "reachability_per_vertical_pixel",
            "launch_platform_vertical_gap_pixels",
            "launch_escape_clearance_pixels",
            "top_danger_player_y_threshold",
            "deep_landing_horizontal_cost",
            "fallback_center_x_pixels",
            "landing_velocity_lookahead_seconds",
            "landing_prediction_max_seconds",
            "landing_release_projection_seconds",
            "special_escape_edge_guard_pixels",
            "special_escape_outward_velocity_threshold_pixels_per_second",
            "special_contact_reacquire_center_tolerance_pixels",
            "wall_evacuation_exit_margin_pixels",
            "wall_guard_velocity_lookahead_seconds",
        ):
            if getattr(self.baseline, name) < 0:
                raise ConfigError(f"baseline.{name} 不可小於 0。")
        if (
            self.baseline.landing_vertical_speed_floor_pixels_per_second
            <= 0
        ):
            raise ConfigError(
                "baseline.landing_vertical_speed_floor_pixels_per_second "
                "必須大於 0。"
            )
        if (
            self.baseline.landing_prediction_max_seconds
            < self.baseline.landing_velocity_lookahead_seconds
        ):
            raise ConfigError(
                "baseline.landing_prediction_max_seconds 不可小於 "
                "landing_velocity_lookahead_seconds。"
            )
        if (
            self.baseline.landing_release_projection_seconds
            > self.baseline.landing_prediction_max_seconds
        ):
            raise ConfigError(
                "baseline.landing_release_projection_seconds 不可大於 "
                "landing_prediction_max_seconds。"
            )
        if self.baseline.direction_switch_release_frames <= 0:
            raise ConfigError(
                "baseline.direction_switch_release_frames 必須大於 0。"
            )
        if self.baseline.emergency_spike_min_health_segments <= 0:
            raise ConfigError(
                "baseline.emergency_spike_min_health_segments 必須大於 0。"
            )
        if self.baseline.recovery_full_health_segments <= 0:
            raise ConfigError(
                "baseline.recovery_full_health_segments 必須大於 0。"
            )
        if self.baseline.special_contact_escape_max_steps <= 0:
            raise ConfigError(
                "baseline.special_contact_escape_max_steps 必須大於 0。"
            )
        for name in (
            "special_contact_direction_commit_steps",
            "special_contact_destination_stability_steps",
            "special_contact_forced_exit_steps",
        ):
            if getattr(self.baseline, name) <= 0:
                raise ConfigError(f"baseline.{name} 必須大於 0。")
        if self.baseline.special_contact_replan_limit < 0:
            raise ConfigError(
                "baseline.special_contact_replan_limit 不可小於 0。"
            )
        if self.baseline.launch_commit_max_steps <= 0:
            raise ConfigError(
                "baseline.launch_commit_max_steps 必須大於 0。"
            )
        if self.baseline.launch_replan_cooldown_steps < 0:
            raise ConfigError(
                "baseline.launch_replan_cooldown_steps 不可小於 0。"
            )
        if self.baseline.support_departure_max_steps <= 0:
            raise ConfigError(
                "baseline.support_departure_max_steps 必須大於 0。"
            )
        if self.baseline.support_departure_lost_frames <= 0:
            raise ConfigError(
                "baseline.support_departure_lost_frames 必須大於 0。"
            )
        if self.baseline.support_departure_abort_cooldown_steps <= 0:
            raise ConfigError(
                "baseline.support_departure_abort_cooldown_steps 必須大於 0。"
            )
        if self.baseline.wall_evacuation_cooldown_steps < 0:
            raise ConfigError(
                "baseline.wall_evacuation_cooldown_steps 不可小於 0。"
            )
        if self.baseline.aligned_platform_dwell_escape_steps <= 0:
            raise ConfigError(
                "baseline.aligned_platform_dwell_escape_steps 必須大於 0。"
            )
        for name in (
            "top_pressure_memory_steps",
            "top_pressure_dropout_continue_steps",
            "top_pressure_support_settle_steps",
        ):
            if getattr(self.baseline, name) <= 0:
                raise ConfigError(f"baseline.{name} 必須大於 0。")
        if (
            self.baseline.top_pressure_dropout_continue_steps
            > self.baseline.top_pressure_memory_steps
        ):
            raise ConfigError(
                "baseline.top_pressure_dropout_continue_steps 不可大於 "
                "top_pressure_memory_steps。"
            )
        if self.baseline.aligned_platform_dwell_gap_tolerance_pixels < 0:
            raise ConfigError(
                "baseline.aligned_platform_dwell_gap_tolerance_pixels 不可小於 0。"
            )
        if self.baseline.playfield_left_pixels < 0:
            raise ConfigError("baseline.playfield_left_pixels 不可小於 0。")
        if (
            self.baseline.playfield_right_pixels
            <= self.baseline.playfield_left_pixels
        ):
            raise ConfigError(
                "baseline.playfield_right_pixels 必須大於 playfield_left_pixels。"
            )
        if (
            self.baseline.wall_guard_margin_pixels < 0
            or self.baseline.wall_guard_margin_pixels * 2
            >= self.baseline.playfield_right_pixels
            - self.baseline.playfield_left_pixels
        ):
            raise ConfigError(
                "baseline.wall_guard_margin_pixels 必須非負且小於 playfield 寬度一半。"
            )
        if (
            self.baseline.wall_evacuation_exit_margin_pixels
            <= self.baseline.wall_guard_margin_pixels
            or self.baseline.wall_evacuation_exit_margin_pixels * 2
            >= self.baseline.playfield_right_pixels
            - self.baseline.playfield_left_pixels
        ):
            raise ConfigError(
                "baseline.wall_evacuation_exit_margin_pixels 必須大於"
                " wall_guard_margin_pixels 且小於 playfield 寬度一半。"
            )
        if self.baseline.post_launch_coast_frames < 0:
            raise ConfigError(
                "baseline.post_launch_coast_frames 不可小於 0。"
            )
        if (
            self.baseline.max_target_vertical_gap_pixels
            <= self.baseline.min_target_vertical_gap_pixels
        ):
            raise ConfigError(
                "baseline.max_target_vertical_gap_pixels 必須大於"
                " min_target_vertical_gap_pixels。"
            )
        allowed_kinds = {
            "normal",
            "spikes",
            "spring",
            "conveyor",
            "flipping",
        }
        if (
            not self.baseline.safe_platform_kinds
            or not all(
                isinstance(kind, str) and kind in allowed_kinds
                for kind in self.baseline.safe_platform_kinds
            )
        ):
            raise ConfigError(
                "baseline.safe_platform_kinds 必須是已知平台類型的非空清單。"
            )

    def validated_exe_path(self) -> Path:
        path = Path(self.game.exe_path).expanduser()
        if not path.is_file() or path.suffix.lower() != ".exe":
            raise ConfigError(f"無效的遊戲 exe 路徑：{path}")
        return path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path = "config.yaml") -> None:
        Path(path).write_text(
            yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
