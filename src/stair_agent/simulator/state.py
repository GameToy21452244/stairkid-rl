from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite


@dataclass(frozen=True)
class ShaftEnvConfig:
    environment_version: str = "ns-shaft-sim-v0.3"
    width: int = 634
    height: int = 431
    enable_calibrated_playfield: bool = True
    playfield_left: float = 40.0
    playfield_right: float = 423.0
    playfield_top: float = 60.0
    playfield_bottom: float = 416.0
    top_hazard_bottom: float = 88.0
    initial_platform_center_y: float = 71.0
    # Policy frequency is independent from fixed-rate physics integration.
    fps: int = 10
    physics_hz: int = 60
    # 60 Hz control is reserved for the manual-only fidelity candidate.  The
    # formal simulator and training paths remain restricted to 8/10/12 Hz.
    allow_manual_60hz_control: bool = False
    distribution: str = "easy"
    max_episode_steps: int = 3000
    player_width: float = 24.0
    player_height: float = 27.0
    horizontal_acceleration: float = 1048.0
    air_control_multiplier: float = 1.0
    max_horizontal_speed: float = 230.0
    release_drag: float = 0.035
    release_deceleration: float | None = None
    reverse_brake_multiplier: float = 1.0
    gravity: float = -192.0
    max_fall_speed: float | None = None
    jump_velocity: float = 95.0
    platform_width: float = 96.0
    platform_height: float = 16.0
    platform_spacing: float = 48.0
    max_platform_shift: float = 180.0
    platform_count: int = 9
    reachability_lookahead: int = 3
    safe_landing_margin: float = 14.0
    easy_max_platform_shift: float = 64.0
    minimum_horizontal_platform_shift: float = 0.0
    generator_max_attempts: int = 1
    hard_max_platform_shift: float = 220.0
    recycle_margin: float = 64.0
    scroll_speed: float = 96.0
    enable_swept_edge_collision: bool = False
    enable_support_ownership: bool = True
    support_departure_velocity_y: float = 0.0
    step_penalty: float = 0.01
    landing_reward: float = 0.05
    floor_reward: float = 1.0
    death_penalty: float = 5.0
    observation_history_frames: int = 4
    include_action_history: bool = True
    enable_health: bool = False
    max_health_segments: int = 12
    initial_health_segments: int = 12
    normal_platform_heal_segments: int = 1
    health_gain_reward_per_segment: float = 0.0
    enable_spikes: bool = False
    spike_damage_segments: int = 5
    spike_damage_penalty_per_segment: float = 0.0
    spike_spawn_probability: float = 0.0
    initial_safe_normal_platforms: int = 3
    minimum_normal_platforms_between_spikes: int = 5
    enable_conveyor: bool = False
    conveyor_velocity_delta: float = 80.0
    enable_spring: bool = False
    spring_jump_velocity: float = 190.0
    spring_spawn_probability: float = 0.0
    minimum_normal_platforms_before_spring: int = 3
    enable_flipping: bool = False
    flipping_active_seconds: float = 1.0
    flipping_inactive_seconds: float = 1.0

    @property
    def dt(self) -> float:
        return 1.0 / self.fps

    @property
    def physics_dt(self) -> float:
        return 1.0 / self.physics_hz

    @property
    def effective_playfield_left(self) -> float:
        return self.playfield_left if self.enable_calibrated_playfield else 0.0

    @property
    def effective_playfield_right(self) -> float:
        return (
            self.playfield_right
            if self.enable_calibrated_playfield
            else float(self.width)
        )

    @property
    def effective_playfield_top(self) -> float:
        return self.playfield_top if self.enable_calibrated_playfield else 0.0

    @property
    def effective_playfield_bottom(self) -> float:
        return (
            self.playfield_bottom
            if self.enable_calibrated_playfield
            else float(self.height)
        )

    @property
    def effective_top_hazard_bottom(self) -> float:
        return (
            self.top_hazard_bottom
            if self.enable_calibrated_playfield
            else 0.0
        )

    @property
    def effective_environment_version(self) -> str:
        features = []
        if self.enable_health:
            features.append("health-v1")
        if self.enable_spikes:
            features.append("spikes-v1")
        if self.spike_spawn_probability > 0:
            features.append("spike-curriculum-v0")
        if self.enable_conveyor:
            features.append("conveyor-v1")
        if self.enable_spring:
            features.append("spring-v1")
        if self.spring_spawn_probability > 0:
            features.append("spring-curriculum-v0")
        if self.enable_flipping:
            features.append("flipping-v1")
        return (
            self.environment_version
            if not features
            else self.environment_version + "+" + "+".join(features)
        )

    def __post_init__(self) -> None:
        supported_policy_fps = self.fps in {8, 10, 12}
        supported_manual_fps = (
            self.fps == 60 and self.allow_manual_60hz_control
        )
        if not (supported_policy_fps or supported_manual_fps):
            raise ValueError(
                "policy fps只支援8、10、12 Hz；"
                "60 Hz僅允許manual fidelity candidate。"
            )
        if self.allow_manual_60hz_control and self.fps != 60:
            raise ValueError(
                "allow_manual_60hz_control只可搭配fps=60。"
            )
        if self.physics_hz != 60:
            raise ValueError("Simulator v0.2 physics_hz 固定為 60。")
        if self.distribution not in {"easy", "calibrated", "hard"}:
            raise ValueError("distribution 只支援 easy、calibrated、hard。")
        if self.reachability_lookahead not in {2, 3}:
            raise ValueError("reachability_lookahead 只支援 2 或 3。")
        if self.horizontal_acceleration <= 0:
            raise ValueError("horizontal_acceleration 必須大於0。")
        if not 0 < self.air_control_multiplier <= 1:
            raise ValueError("air_control_multiplier 必須介於0與1。")
        if self.max_horizontal_speed <= 0:
            raise ValueError("max_horizontal_speed 必須大於0。")
        if (
            self.release_deceleration is not None
            and self.release_deceleration <= 0
        ):
            raise ValueError("release_deceleration 必須大於0或為None。")
        if self.reverse_brake_multiplier < 1:
            raise ValueError("reverse_brake_multiplier 不可小於1。")
        if self.max_fall_speed is not None and self.max_fall_speed <= 0:
            raise ValueError("max_fall_speed 必須大於0或為None。")
        if self.minimum_horizontal_platform_shift < 0:
            raise ValueError("minimum_horizontal_platform_shift 不可小於0。")
        if self.minimum_horizontal_platform_shift > min(
            self.easy_max_platform_shift,
            self.max_platform_shift,
            self.hard_max_platform_shift,
        ):
            raise ValueError(
                "minimum_horizontal_platform_shift 不可大於最大shift。"
            )
        if self.generator_max_attempts < 1:
            raise ValueError("generator_max_attempts 必須至少為1。")
        if not (
            0.0 <= self.playfield_left < self.playfield_right <= self.width
        ):
            raise ValueError("playfield 左右邊界必須位於畫布內。")
        if not (
            0.0 <= self.playfield_top
            < self.top_hazard_bottom
            < self.playfield_bottom
            <= self.height
        ):
            raise ValueError("playfield 垂直邊界或頂部危險區無效。")
        if (
            self.playfield_right - self.playfield_left
            < self.platform_width
        ):
            raise ValueError("playfield 寬度不可小於平台寬度。")
        if self.max_health_segments <= 0:
            raise ValueError("max_health_segments 必須大於 0。")
        if not 0 <= self.initial_health_segments <= self.max_health_segments:
            raise ValueError("initial_health_segments 必須介於 0 與 max 之間。")
        if self.normal_platform_heal_segments < 0:
            raise ValueError("normal_platform_heal_segments 不可小於 0。")
        if self.enable_spikes and not self.enable_health:
            raise ValueError("enable_spikes 需要 enable_health。")
        if self.spike_damage_segments <= 0:
            raise ValueError("spike_damage_segments 必須大於 0。")
        if not 0.0 <= self.spike_spawn_probability <= 1.0:
            raise ValueError(
                "spike_spawn_probability 必須介於 0 與 1。"
            )
        if self.initial_safe_normal_platforms < 1:
            raise ValueError(
                "initial_safe_normal_platforms 必須至少為 1。"
            )
        if self.minimum_normal_platforms_between_spikes < 0:
            raise ValueError(
                "minimum_normal_platforms_between_spikes 不可小於 0。"
            )
        if self.spike_spawn_probability > 0:
            if not self.enable_spikes:
                raise ValueError(
                    "spike_spawn_probability > 0 需要 enable_spikes。"
                )
            if self.normal_platform_heal_segments <= 0:
                raise ValueError(
                    "spike curriculum 需要普通平台回血。"
                )
            recovery_platforms = ceil(
                self.spike_damage_segments
                / self.normal_platform_heal_segments
            )
            if (
                self.minimum_normal_platforms_between_spikes
                < recovery_platforms
            ):
                raise ValueError(
                    "尖刺間普通平台數不足以恢復一次傷害。"
                )
        if self.conveyor_velocity_delta <= 0:
            raise ValueError("conveyor_velocity_delta 必須大於 0。")
        if not isfinite(self.support_departure_velocity_y):
            raise ValueError(
                "support_departure_velocity_y 必須是有限數值。"
            )
        if self.spring_jump_velocity <= self.jump_velocity:
            raise ValueError(
                "spring_jump_velocity 必須大於一般 jump_velocity。"
            )
        if not 0.0 <= self.spring_spawn_probability <= 1.0:
            raise ValueError(
                "spring_spawn_probability 必須介於 0 與 1。"
            )
        if self.minimum_normal_platforms_before_spring < 1:
            raise ValueError(
                "minimum_normal_platforms_before_spring 不可小於 1。"
            )
        if self.spring_spawn_probability > 0 and not self.enable_spring:
            raise ValueError(
                "spring_spawn_probability > 0 需要 enable_spring。"
            )
        if self.flipping_active_seconds <= 0:
            raise ValueError("flipping_active_seconds 必須大於 0。")
        if self.flipping_inactive_seconds <= 0:
            raise ValueError("flipping_inactive_seconds 必須大於 0。")


@dataclass(frozen=True)
class SupportDepartureRecord:
    source_floor: int
    clearance: float


@dataclass(frozen=True)
class SimulatorStep:
    events: tuple[str, ...]
    terminated: bool
    terminal_reason: str | None
    health_delta: int = 0
    conveyor_velocity_delta_x: float = 0.0
    spring_velocity_delta_y: float = 0.0
    support_departures: tuple[SupportDepartureRecord, ...] = ()
