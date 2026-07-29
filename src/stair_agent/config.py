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
    restart_duration_ms: int = 200
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
    player_min_height: int = 15
    player_max_height: int = 50
    player_dilate_width: int = 7
    player_dilate_height: int = 9
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


@dataclass
class EventsConfig:
    landing_contact_gap: int = 6
    spring_contact_gap: int = 12
    correlation_frames: int = 5


@dataclass
class EnvironmentConfig:
    max_episode_steps: int = 3000
    floor_reward: float = 1.0
    damage_penalty_per_segment: float = 0.2
    death_penalty: float = 5.0
    velocity_scale: float = 500.0
    max_platforms_per_type: int = 8
    auto_restart_on_reset: bool = False
    reset_required_consecutive_frames: int = 3
    reset_max_observation_frames: int = 30
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
    learning_rate: float = 0.0003
    gamma: float = 0.99
    gae_lambda: float = 0.95
    ent_coef: float = 0.01
    seed: int = 42
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
    post_launch_coast_frames: int = 2
    fallback_center_x_pixels: float = 231.5
    top_danger_player_y_threshold: float = 140.0
    deep_landing_horizontal_cost: float = 0.75
    emergency_spike_min_health_segments: int = 6
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
        if self.controls.restart_duration_ms <= 0:
            raise ConfigError("controls.restart_duration_ms 必須大於 0。")
        if not 0.0 < self.detection.dialog_threshold <= 1.0:
            raise ConfigError("detection.dialog_threshold 必須介於 0 與 1 之間。")
        if self.detection.search_margin < 0:
            raise ConfigError("detection.search_margin 不可小於 0。")
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
        for name in (
            "floor_reward",
            "damage_penalty_per_segment",
            "death_penalty",
            "reset_post_action_delay_seconds",
        ):
            if getattr(self.environment, name) < 0:
                raise ConfigError(f"environment.{name} 不可小於 0。")
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
        ):
            if getattr(self.baseline, name) < 0:
                raise ConfigError(f"baseline.{name} 不可小於 0。")
        if self.baseline.direction_switch_release_frames <= 0:
            raise ConfigError(
                "baseline.direction_switch_release_frames 必須大於 0。"
            )
        if self.baseline.emergency_spike_min_health_segments <= 0:
            raise ConfigError(
                "baseline.emergency_spike_min_health_segments 必須大於 0。"
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
