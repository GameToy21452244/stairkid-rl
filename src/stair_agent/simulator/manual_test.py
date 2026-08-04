from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from .physics import ShaftSimulator
from .scenarios import (
    configure_conveyor_landing,
    configure_flipping_landing,
    configure_normal_healing_landing,
    configure_spring_landing,
    configure_spike_landing,
)
from .state import ShaftEnvConfig


MANUAL_SEED_MINIMUM = 900_000
DEFAULT_MANUAL_SEED = 900_001
DEFAULT_OUTPUT_ROOT = Path("artifacts") / "manual_simulator_test"
RATING_VALUES = (
    "very_close",
    "close",
    "noticeably_different",
    "very_different",
    "unknown",
)
RATING_TAGS = (
    "acceleration_too_fast",
    "acceleration_too_slow",
    "release_stops_too_fast",
    "release_slides_too_far",
    "reverse_too_fast",
    "reverse_too_slow",
    "edge_departure_too_early",
    "edge_departure_too_late",
    "landing_too_bouncy",
    "landing_too_sticky",
    "scroll_too_fast",
    "scroll_too_slow",
    "top_terminal_too_early",
    "top_terminal_too_late",
    "bottom_terminal_too_early",
    "bottom_terminal_too_late",
    "platform_semantics_wrong",
    "visual_only_difference",
    "other",
)
CALIBRATION_QUESTIONS = (
    "horizontal_acceleration_closer",
    "release_glide_closer",
    "reverse_braking_closer",
    "platform_tunneling_still_occurs",
    "platform_scroll_still_too_fast",
    "platform_density_closer",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def validate_manual_seed(seed: int) -> int:
    if seed < MANUAL_SEED_MINIMUM:
        raise ValueError(
            f"manual-only seed 必須 >= {MANUAL_SEED_MINIMUM}；"
            "formal development／holdout partition 一律拒絕。"
        )
    return seed


ScenarioSetup = Callable[[ShaftSimulator], None]


@dataclass(frozen=True)
class ManualScenario:
    scenario_id: str
    name: str
    title: str
    purpose: str
    validation_status: str
    special_platform: bool
    config: ShaftEnvConfig
    setup: ScenarioSetup
    formal_evaluation_allowed: bool = False


def _first_platform(simulator: ShaftSimulator):
    return min(simulator.platforms, key=lambda item: item.floor_index)


def _stand_on_first_platform(
    simulator: ShaftSimulator,
    *,
    velocity_x: float = 0.0,
) -> None:
    platform = _first_platform(simulator)
    simulator.supported_floor = platform.floor_index
    simulator.player.body.position = (
        platform.center_x,
        platform.top + simulator.player.height / 2,
    )
    simulator.player.body.velocity = (
        velocity_x,
        simulator.config.scroll_speed,
    )


def _normal_setup(simulator: ShaftSimulator) -> None:
    _stand_on_first_platform(simulator)


def _release_setup(simulator: ShaftSimulator) -> None:
    _stand_on_first_platform(simulator, velocity_x=160.0)


def _reverse_setup(simulator: ShaftSimulator) -> None:
    _stand_on_first_platform(simulator, velocity_x=180.0)


def _landing_setup(simulator: ShaftSimulator) -> None:
    configure_normal_healing_landing(
        simulator,
        health_segments=simulator.health_segments,
        fall_speed=-180.0,
    )


def _top_setup(simulator: ShaftSimulator) -> None:
    config = simulator.config
    simulator.supported_floor = None
    simulator.player.body.position = (
        (config.effective_playfield_left + config.effective_playfield_right)
        / 2,
        config.height
        - (config.effective_top_hazard_bottom + 2.0)
        - simulator.player.height / 2,
    )
    simulator.player.body.velocity = (0.0, 100.0)


def _bottom_setup(simulator: ShaftSimulator) -> None:
    config = simulator.config
    simulator.supported_floor = None
    simulator.player.body.position = (
        (config.effective_playfield_left + config.effective_playfield_right)
        / 2,
        config.height
        - (config.effective_playfield_bottom - 2.0)
        - simulator.player.height / 2,
    )
    simulator.player.body.velocity = (0.0, -120.0)


def _spring_setup(simulator: ShaftSimulator) -> None:
    configure_spring_landing(simulator, fall_speed=-180.0)


def _conveyor_left_setup(simulator: ShaftSimulator) -> None:
    configure_conveyor_landing(
        simulator,
        direction="left",
        fall_speed=-180.0,
    )


def _conveyor_right_setup(simulator: ShaftSimulator) -> None:
    configure_conveyor_landing(
        simulator,
        direction="right",
        fall_speed=-180.0,
    )


def _spike_setup(simulator: ShaftSimulator) -> None:
    configure_spike_landing(
        simulator,
        health_segments=simulator.config.max_health_segments,
        fall_speed=-180.0,
    )


def _flipping_active_setup(simulator: ShaftSimulator) -> None:
    configure_flipping_landing(
        simulator,
        active=True,
        fall_speed=-180.0,
    )


def _flipping_inactive_setup(simulator: ShaftSimulator) -> None:
    configure_flipping_landing(
        simulator,
        active=False,
        fall_speed=-180.0,
    )


def _healing_setup(simulator: ShaftSimulator) -> None:
    configure_normal_healing_landing(
        simulator,
        health_segments=max(1, simulator.config.max_health_segments // 2),
        fall_speed=-180.0,
    )


def _normal_config(**changes: Any) -> ShaftEnvConfig:
    values: dict[str, Any] = {
        "environment_version": "ns-shaft-sim-v0.4-calibration-candidate",
        "distribution": "easy",
        "fps": 10,
        "physics_hz": 60,
        "horizontal_acceleration": 560.0,
        "air_control_multiplier": 0.85,
        "release_deceleration": 960.0,
        "reverse_brake_multiplier": 1.25,
        "easy_max_platform_shift": 160.0,
        "minimum_horizontal_platform_shift": 24.0,
        "generator_max_attempts": 8,
        "scroll_speed": 80.0,
        "enable_swept_edge_collision": True,
    }
    values.update(changes)
    return ShaftEnvConfig(**values)


def calibration_profile_config(
    config: ShaftEnvConfig,
    profile: str,
) -> ShaftEnvConfig:
    if profile == "after":
        return replace(
            config,
            environment_version="ns-shaft-sim-v0.4-calibration-candidate",
            horizontal_acceleration=560.0,
            air_control_multiplier=0.85,
            release_deceleration=960.0,
            reverse_brake_multiplier=1.25,
            easy_max_platform_shift=160.0,
            minimum_horizontal_platform_shift=24.0,
            generator_max_attempts=8,
            scroll_speed=80.0,
            enable_swept_edge_collision=True,
        )
    if profile != "before":
        raise ValueError("calibration profile只支援before或after。")
    return replace(
        config,
        environment_version="ns-shaft-sim-v0.3",
        horizontal_acceleration=1048.0,
        air_control_multiplier=1.0,
        release_drag=0.035,
        release_deceleration=None,
        reverse_brake_multiplier=1.0,
        max_fall_speed=None,
        easy_max_platform_shift=64.0,
        minimum_horizontal_platform_shift=0.0,
        generator_max_attempts=1,
        scroll_speed=96.0,
        enable_swept_edge_collision=False,
    )


SCENARIOS = (
    ManualScenario(
        "M01",
        "normal_baseline",
        "Normal free play",
        "一般移動、落下、捲動與整體手感",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(),
        _normal_setup,
    ),
    ManualScenario(
        "M02",
        "horizontal_acceleration",
        "Horizontal acceleration",
        "在寬平台比較 LEFT／RIGHT 起步加速與位移",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(
            scroll_speed=0.0,
            platform_width=240.0,
            easy_max_platform_shift=24.0,
        ),
        _normal_setup,
    ),
    ManualScenario(
        "M03",
        "release_damping",
        "Release damping",
        "以固定初速觀察 RELEASE 滑行與停止時間",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(
            scroll_speed=0.0,
            platform_width=240.0,
            easy_max_platform_shift=24.0,
        ),
        _release_setup,
    ),
    ManualScenario(
        "M04",
        "reverse_braking",
        "Reverse braking",
        "以固定 RIGHT 初速測試 LEFT 煞車與反向；重設後可反向操作",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(
            scroll_speed=0.0,
            platform_width=240.0,
            easy_max_platform_shift=24.0,
        ),
        _reverse_setup,
    ),
    ManualScenario(
        "M05",
        "platform_edge_departure",
        "Platform edge departure",
        "由寬平台中央移向左右邊緣，檢查支撐離開語意",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(
            scroll_speed=0.0,
            platform_width=200.0,
            easy_max_platform_shift=24.0,
        ),
        _normal_setup,
    ),
    ManualScenario(
        "M06",
        "landing_support",
        "Landing and support",
        "固定落下位置，檢查 landing、support與平台上升跟隨",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(),
        _landing_setup,
    ),
    ManualScenario(
        "M07",
        "top_terminal",
        "Top terminal",
        "由頂部危險區附近開始，檢查 top terminal timing與headroom",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(scroll_speed=0.0),
        _top_setup,
    ),
    ManualScenario(
        "M08",
        "bottom_terminal",
        "Bottom terminal",
        "由底部邊界附近落下，檢查 bottom terminal timing",
        "MANUAL_ONLY_NOT_FORMALLY_VALIDATED",
        False,
        _normal_config(scroll_speed=0.0),
        _bottom_setup,
    ),
    ManualScenario(
        "M09",
        "spring",
        "Spring platform",
        "固定 spring landing與bounce",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_spring=True),
        _spring_setup,
    ),
    ManualScenario(
        "M10",
        "conveyor_left",
        "Conveyor left",
        "固定左向conveyor landing與速度變化",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_conveyor=True),
        _conveyor_left_setup,
    ),
    ManualScenario(
        "M11",
        "conveyor_right",
        "Conveyor right",
        "固定右向conveyor landing與速度變化",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_conveyor=True),
        _conveyor_right_setup,
    ),
    ManualScenario(
        "M12",
        "spikes",
        "Spikes platform",
        "固定spike landing、damage與health",
        "PROVISIONAL",
        True,
        _normal_config(
            scroll_speed=0.0,
            enable_health=True,
            enable_spikes=True,
        ),
        _spike_setup,
    ),
    ManualScenario(
        "M13",
        "flipping_active",
        "Flipping active",
        "固定active flipping platform landing",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_flipping=True),
        _flipping_active_setup,
    ),
    ManualScenario(
        "M14",
        "flipping_inactive",
        "Flipping inactive",
        "固定inactive flipping platform穿越／失去支撐",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_flipping=True),
        _flipping_inactive_setup,
    ),
    ManualScenario(
        "M15",
        "normal_healing",
        "Normal-platform healing",
        "固定低health落在normal平台；專案尚無獨立healing kind",
        "PROVISIONAL",
        True,
        _normal_config(scroll_speed=0.0, enable_health=True),
        _healing_setup,
    ),
)
_SCENARIO_BY_NAME = {scenario.name: scenario for scenario in SCENARIOS}


def list_manual_scenarios() -> tuple[ManualScenario, ...]:
    return SCENARIOS


def get_manual_scenario(name: str) -> ManualScenario:
    try:
        return _SCENARIO_BY_NAME[name]
    except KeyError as exc:
        choices = ", ".join(_SCENARIO_BY_NAME)
        raise ValueError(f"未知manual scenario {name!r}；可用：{choices}") from exc


def build_manual_environment(
    scenario: str,
    *,
    seed: int,
    profile: str = "after",
) -> tuple[ShaftEnv, ManualScenario]:
    definition = get_manual_scenario(scenario)
    manual_seed = validate_manual_seed(seed)
    env = ShaftEnv(
        config=calibration_profile_config(definition.config, profile),
        render_mode="rgb_array",
    )
    try:
        env.reset(seed=manual_seed)
        if env.simulator is None:
            raise RuntimeError("manual simulator reset後沒有physics instance。")
        definition.setup(env.simulator)
    except Exception:
        env.close()
        raise
    return env, definition


class ManualInputState:
    _LEFT_KEYS = frozenset({"left", "a"})
    _RIGHT_KEYS = frozenset({"right", "d"})

    def __init__(self) -> None:
        self._held: set[str] = set()
        self.focused = True

    @staticmethod
    def _normalize(key: str) -> str:
        return key.strip().lower().replace("arrow", "")

    def key_down(self, key: str) -> None:
        normalized = self._normalize(key)
        if normalized in self._LEFT_KEYS | self._RIGHT_KEYS:
            self._held.add(normalized)

    def key_up(self, key: str) -> None:
        self._held.discard(self._normalize(key))

    def clear(self) -> None:
        self._held.clear()

    def focus_lost(self) -> None:
        self.focused = False
        self.clear()

    def focus_gained(self) -> None:
        self.focused = True

    @property
    def held_keys(self) -> frozenset[str]:
        return frozenset(self._held)

    @property
    def action(self) -> Action:
        if not self.focused:
            return Action.RELEASE_ALL
        left = bool(self._held & self._LEFT_KEYS)
        right = bool(self._held & self._RIGHT_KEYS)
        if left == right:
            return Action.RELEASE_ALL
        return Action.LEFT if left else Action.RIGHT


@dataclass
class RatingDraft:
    rating: str = "unknown"
    selected_tags: set[str] | None = None
    tag_index: int = 0
    note: str = ""
    note_entry: bool = False
    question_index: int = 0
    calibration_answers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.selected_tags is None:
            self.selected_tags = set()
        if self.calibration_answers is None:
            self.calibration_answers = {}


class ManualSimulatorSession:
    CSV_FIELDS = (
        "timestamp_utc",
        "scenario_id",
        "scenario",
        "validation_status",
        "calibration_profile",
        "seed",
        "step",
        "simulator_time",
        "action",
        "previous_action",
        "player_x",
        "player_y",
        "velocity_x",
        "velocity_y",
        "player_bbox",
        "airborne",
        "support_floor",
        "support_kind",
        "deepest_floor",
        "headroom",
        "health",
        "terminal_reason",
        "events",
        "action_switches",
        "last_reversal_step",
        "left_hold_seconds",
        "right_hold_seconds",
        "release_seconds",
        "horizontal_acceleration",
        "scroll_speed",
        "physics_dt",
        "physics_substeps",
        "visible_platform_count",
        "generator_profile",
        "platforms",
    )

    def __init__(
        self,
        *,
        scenario: str = "normal_baseline",
        seed: int = DEFAULT_MANUAL_SEED,
        output_root: Path = DEFAULT_OUTPUT_ROOT,
        session_id: str | None = None,
        display_fps: int = 60,
        show_debug: bool = False,
        record_video: bool = False,
        calibration_profile: str = "after",
    ) -> None:
        self.seed = validate_manual_seed(seed)
        if display_fps <= 0:
            raise ValueError("display fps 必須大於0。")
        self.display_fps = display_fps
        if calibration_profile not in {"before", "after"}:
            raise ValueError("calibration_profile只支援before或after。")
        self.calibration_profile = calibration_profile
        self.output_root = Path(output_root)
        self.session_id = session_id or (
            "manual_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        )
        self.output_dir = self.output_root / self.session_id
        if self.output_dir.exists():
            raise FileExistsError(f"拒絕覆寫manual session：{self.output_dir}")
        self.output_dir.mkdir(parents=True)
        self.started_at = _utc_now()
        self.ended_at: str | None = None
        self.input_state = ManualInputState()
        self.paused = False
        self.show_debug = show_debug
        self.video_recording = record_video
        self.rating_draft: RatingDraft | None = None
        self._paused_before_rating = False
        self._closed = False
        self._events: list[dict[str, Any]] = []
        self._ratings: list[dict[str, Any]] = []
        self._scenario_history: list[dict[str, Any]] = []
        self._video_writer = None
        self._frame_sequence_dir: Path | None = None
        self._recorded_frames = 0
        self.step_count = 0
        self.total_step_count = 0
        self.action_switches = 0
        self.previous_action = Action.RELEASE_ALL
        self.last_directional_action: Action | None = None
        self.last_reversal_step: int | None = None
        self._action_duration = 0.0
        self.terminal_reason: str | None = None
        self.last_info: dict[str, Any] = {}
        self._scenario_index = next(
            index
            for index, item in enumerate(SCENARIOS)
            if item.name == scenario
        )
        self.env, self.scenario = build_manual_environment(
            scenario,
            seed=self.seed,
            profile=self.calibration_profile,
        )
        self._csv_handle = (
            self.output_dir / "frame_or_step_log.csv"
        ).open("w", encoding="utf-8", newline="")
        self._csv_writer = csv.DictWriter(
            self._csv_handle,
            fieldnames=self.CSV_FIELDS,
        )
        self._csv_writer.writeheader()
        self._event("session_started")
        self._record_scenario_start()

    def _event(self, event_type: str, **details: Any) -> None:
        self._events.append(
            {
                "timestamp_utc": _utc_now(),
                "session_step": self.total_step_count,
                "scenario_id": self.scenario.scenario_id,
                "scenario": self.scenario.name,
                "type": event_type,
                **details,
            }
        )

    def _record_scenario_start(self) -> None:
        self._scenario_history.append(
            {
                "scenario_id": self.scenario.scenario_id,
                "scenario": self.scenario.name,
                "validation_status": self.scenario.validation_status,
                "started_at": _utc_now(),
                "seed": self.seed,
            }
        )

    def _replace_environment(self, scenario: ManualScenario) -> None:
        self.env.close()
        self.env, self.scenario = build_manual_environment(
            scenario.name,
            seed=self.seed,
            profile=self.calibration_profile,
        )
        self.step_count = 0
        self.previous_action = Action.RELEASE_ALL
        self.last_directional_action = None
        self.last_reversal_step = None
        self._action_duration = 0.0
        self.terminal_reason = None
        self.last_info = {}
        self.input_state.clear()
        self.input_state.focus_gained()
        self.paused = False
        self.rating_draft = None
        self._record_scenario_start()

    def reset_scenario(self) -> None:
        self._event("scenario_reset")
        self._replace_environment(self.scenario)

    def next_scenario(self) -> None:
        self._scenario_index = (self._scenario_index + 1) % len(SCENARIOS)
        next_definition = SCENARIOS[self._scenario_index]
        self._event("scenario_switch", next_scenario=next_definition.name)
        self._replace_environment(next_definition)

    def toggle_calibration_profile(self) -> None:
        self.calibration_profile = (
            "before" if self.calibration_profile == "after" else "after"
        )
        self._event(
            "calibration_profile_changed",
            profile=self.calibration_profile,
        )
        self._replace_environment(self.scenario)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.input_state.clear()
        self._event("pause_changed", paused=self.paused)

    def toggle_debug(self) -> None:
        self.show_debug = not self.show_debug
        self._event("debug_overlay_changed", visible=self.show_debug)

    def toggle_recording(self) -> None:
        self.video_recording = not self.video_recording
        self._event("video_recording_changed", active=self.video_recording)

    def focus_lost(self) -> None:
        self.input_state.focus_lost()
        self._event("focus_lost_release_all")

    def focus_gained(self) -> None:
        self.input_state.focus_gained()
        self._event("focus_gained")

    def begin_rating(self, *, trigger: str = "manual_marker") -> None:
        if self.rating_draft is not None:
            return
        self._paused_before_rating = self.paused
        self.paused = True
        self.input_state.clear()
        self.rating_draft = RatingDraft()
        self._event("rating_opened", trigger=trigger)

    def save_rating(self) -> None:
        draft = self.rating_draft
        if draft is None:
            return
        self.add_rating(
            rating=draft.rating,
            tags=sorted(draft.selected_tags or set()),
            note=draft.note,
            calibration_answers=draft.calibration_answers or {},
        )
        self.rating_draft = None
        self.paused = self._paused_before_rating or self.terminal_reason is not None

    def add_rating(
        self,
        *,
        rating: str,
        tags: Iterable[str] = (),
        note: str = "",
        calibration_answers: dict[str, str] | None = None,
    ) -> None:
        if rating not in RATING_VALUES:
            raise ValueError(f"不支援的manual rating：{rating}")
        tag_list = sorted(set(tags))
        unknown = set(tag_list) - set(RATING_TAGS)
        if unknown:
            raise ValueError(f"不支援的manual rating tags：{sorted(unknown)}")
        answers = dict(calibration_answers or {})
        if set(answers) - set(CALIBRATION_QUESTIONS):
            raise ValueError("manual calibration answers包含未知問題。")
        if set(answers.values()) - set(RATING_VALUES):
            raise ValueError("manual calibration answers包含未知評分。")
        row = {
            "timestamp_utc": _utc_now(),
            "scenario_id": self.scenario.scenario_id,
            "scenario": self.scenario.name,
            "step": self.step_count,
            "rating": rating,
            "tags": tag_list,
            "note": note[:500],
            "calibration_answers": answers,
            "formal_evidence": False,
        }
        self._ratings.append(row)
        self._event("manual_rating_saved", rating=rating, tags=tag_list)

    def _platform_rows(self) -> list[dict[str, Any]]:
        simulator = self.env.simulator
        if simulator is None:
            return []
        rows = []
        for platform in sorted(
            simulator.platforms,
            key=lambda item: item.floor_index,
        ):
            screen_top = simulator.config.height - platform.top
            if -platform.height <= screen_top <= simulator.config.height:
                rows.append(
                    {
                        "floor": platform.floor_index,
                        "kind": platform.kind,
                        "left": round(float(platform.left), 3),
                        "right": round(float(platform.right), 3),
                        "top": round(float(screen_top), 3),
                        "height": round(float(platform.height), 3),
                        "active": simulator.platform_is_active(platform),
                        "owns_support": (
                            simulator.supported_floor == platform.floor_index
                        ),
                        "movement": "up" if simulator.config.scroll_speed else "static",
                        "speed": float(simulator.config.scroll_speed),
                        "collision_surface": "top",
                    }
                )
        return rows

    def step_once(self) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("manual session已關閉。")
        if self.paused:
            raise RuntimeError("manual session暫停中，不可step。")
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("manual simulator尚未reset。")
        action = self.input_state.action
        if action != self.previous_action:
            self.action_switches += 1
            self._action_duration = 0.0
        else:
            self._action_duration += self.env.config.dt
        if action in {Action.LEFT, Action.RIGHT}:
            if (
                self.last_directional_action is not None
                and action != self.last_directional_action
            ):
                self.last_reversal_step = self.step_count + 1
                self._event(
                    "direction_reversal",
                    previous=self.last_directional_action.name,
                    current=action.name,
                )
            self.last_directional_action = action

        _observation, _reward, terminated, truncated, info = self.env.step(
            int(action)
        )
        self.step_count += 1
        self.total_step_count += 1
        self.last_info = info
        self.terminal_reason = info["terminal_reason"]
        body = simulator.player.body
        screen_y = self.env.config.height - float(body.position.y)
        player_left = float(body.position.x) - simulator.player.width / 2
        player_top = screen_y - simulator.player.height / 2
        support = simulator.supported_platform
        headroom = player_top - self.env.config.effective_top_hazard_bottom
        row = {
            "timestamp_utc": _utc_now(),
            "scenario_id": self.scenario.scenario_id,
            "scenario": self.scenario.name,
            "validation_status": self.scenario.validation_status,
            "calibration_profile": self.calibration_profile,
            "seed": self.seed,
            "step": self.step_count,
            "simulator_time": round(float(simulator.elapsed_seconds), 6),
            "action": action.name,
            "previous_action": self.previous_action.name,
            "player_x": round(float(body.position.x), 6),
            "player_y": round(float(body.position.y), 6),
            "velocity_x": round(float(body.velocity.x), 6),
            "velocity_y": round(float(body.velocity.y), 6),
            "player_bbox": json.dumps(
                [
                    round(player_left, 3),
                    round(player_top, 3),
                    round(float(simulator.player.width), 3),
                    round(float(simulator.player.height), 3),
                ]
            ),
            "airborne": support is None,
            "support_floor": simulator.supported_floor,
            "support_kind": support.kind if support else None,
            "deepest_floor": simulator.deepest_floor,
            "headroom": round(float(headroom), 6),
            "health": simulator.health_segments,
            "terminal_reason": self.terminal_reason,
            "events": json.dumps(info["events"], ensure_ascii=False),
            "action_switches": self.action_switches,
            "last_reversal_step": self.last_reversal_step,
            "left_hold_seconds": (
                round(self._action_duration, 6) if action is Action.LEFT else 0.0
            ),
            "right_hold_seconds": (
                round(self._action_duration, 6) if action is Action.RIGHT else 0.0
            ),
            "release_seconds": (
                round(self._action_duration, 6)
                if action is Action.RELEASE_ALL
                else 0.0
            ),
            "horizontal_acceleration": (
                -self.env.config.horizontal_acceleration
                if action is Action.LEFT
                else (
                    self.env.config.horizontal_acceleration
                    if action is Action.RIGHT
                    else 0.0
                )
            ),
            "scroll_speed": self.env.config.scroll_speed,
            "physics_dt": self.env.config.physics_dt,
            "physics_substeps": self.env.config.physics_hz / self.env.config.fps,
            "visible_platform_count": len(self._platform_rows()),
            "generator_profile": self.env.config.distribution,
            "platforms": json.dumps(
                self._platform_rows(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        self._csv_writer.writerow(row)
        self._csv_handle.flush()
        for event in info["events"]:
            self._event("simulator_event", event=str(event))
        if terminated or truncated:
            self._event(
                "scenario_ended",
                terminal_reason=self.terminal_reason,
                truncated=truncated,
            )
            self.begin_rating(trigger="scenario_ended")
        self.previous_action = action
        return row

    def _draw_text(
        self,
        frame: np.ndarray,
        text: str,
        origin: tuple[int, int],
        *,
        color: tuple[int, int, int] = (240, 240, 240),
        scale: float = 0.42,
    ) -> None:
        import cv2

        cv2.putText(
            frame,
            text,
            origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            1,
            cv2.LINE_AA,
        )

    def render_frame(self, *, measured_fps: float = 0.0) -> np.ndarray:
        simulator = self.env.simulator
        if simulator is None:
            raise RuntimeError("manual simulator尚未reset。")
        frame = self.env.renderer.rgb_array(simulator, None).copy()
        import cv2

        header = frame.copy()
        cv2.rectangle(header, (0, 0), (frame.shape[1] - 1, 49), (0, 0, 0), -1)
        cv2.addWeighted(header, 0.72, frame, 0.28, 0, frame)
        action = self.input_state.action
        self._draw_text(
            frame,
            (
                f"{self.scenario.scenario_id} {self.scenario.name} "
                f"[{self.scenario.validation_status}] profile={self.calibration_profile}"
            ),
            (7, 17),
            color=(255, 190, 80) if self.scenario.special_platform else (180, 245, 190),
            scale=0.43,
        )
        self._draw_text(
            frame,
            (
                f"seed={self.seed} step={self.step_count} sim={simulator.elapsed_seconds:.2f}s "
                f"render={measured_fps:.1f} physics={self.env.config.physics_hz}Hz "
                f"action={action.name} paused={self.paused} rec={self.video_recording}"
            ),
            (7, 39),
            scale=0.39,
        )
        if self.show_debug:
            overlay = frame.copy()
            cv2.rectangle(overlay, (3, 52), (630, 178), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)
            body = simulator.player.body
            screen_y = self.env.config.height - float(body.position.y)
            player_left = int(round(float(body.position.x) - simulator.player.width / 2))
            player_top = int(round(screen_y - simulator.player.height / 2))
            cv2.rectangle(
                frame,
                (player_left, player_top),
                (
                    player_left + int(round(simulator.player.width)),
                    player_top + int(round(simulator.player.height)),
                ),
                (255, 255, 255),
                1,
            )
            support = simulator.supported_platform
            headroom = player_top - self.env.config.effective_top_hazard_bottom
            lines = (
                f"x/y={body.position.x:.1f}/{body.position.y:.1f} vx/vy={body.velocity.x:.1f}/{body.velocity.y:.1f}",
                f"airborne={support is None} support={simulator.supported_floor}/{support.kind if support else '-'} floor={simulator.deepest_floor}",
                f"headroom={headroom:.1f} health={simulator.health_segments} terminal={self.terminal_reason or '-'}",
                f"hold={self._action_duration:.2f}s reversal_step={self.last_reversal_step} switches={self.action_switches}",
                f"dt={self.env.config.physics_dt:.4f} substeps={self.env.config.physics_hz / self.env.config.fps:.1f} scroll={self.env.config.scroll_speed:.1f} visible={len(self._platform_rows())}",
                f"profile={self.env.config.distribution} collision={getattr(simulator, 'last_collision_diagnostic', None)} events={self.last_info.get('events', [])}",
                "F1 debug F2 video F3 rating B before/after R reset N next P pause ESC exit",
            )
            for index, line in enumerate(lines):
                self._draw_text(frame, line, (8, 70 + index * 19), scale=0.38)
            for platform in self._platform_rows():
                left = int(round(platform["left"]))
                right = int(round(platform["right"]))
                top = int(round(platform["top"]))
                bottom = top + int(round(platform["height"]))
                color = (255, 255, 255) if platform["active"] else (130, 130, 130)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 1)
                label = (
                    f"F{platform['floor']} {platform['kind']} "
                    f"{'SUP' if platform['owns_support'] else ''} "
                    f"{'ON' if platform['active'] else 'OFF'}"
                )
                self._draw_text(
                    frame,
                    label,
                    (left, max(12, top - 3)),
                    color=color,
                    scale=0.31,
                )
        if self.rating_draft is not None:
            draft = self.rating_draft
            overlay = frame.copy()
            cv2.rectangle(overlay, (45, 205), (590, 420), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)
            selected_tag = RATING_TAGS[draft.tag_index]
            question = CALIBRATION_QUESTIONS[draft.question_index]
            answer = (draft.calibration_answers or {}).get(question, "unknown")
            rating_lines = (
                "MANUAL RATING (paused)",
                "1 very_close  2 close  3 noticeable  4 very_different  5 unknown",
                f"rating={draft.rating}",
                f"question {draft.question_index + 1}/6={question}: {answer} (Q next)",
                f"tag=[{selected_tag}]  Up/Down choose, Enter toggle",
                f"selected={','.join(sorted(draft.selected_tags or set())) or '-'}",
                f"Tab note mode={draft.note_entry}; note={draft.note[-55:]}",
                "F3 save/close rating; ESC safely exits whole session",
            )
            for index, line in enumerate(rating_lines):
                self._draw_text(
                    frame,
                    line,
                    (58, 229 + index * 27),
                    color=(245, 225, 150) if index == 0 else (240, 240, 240),
                    scale=0.40,
                )
        return frame

    def record_frame(self, frame: np.ndarray) -> None:
        if not self.video_recording:
            return
        import cv2

        if self._video_writer is None and self._frame_sequence_dir is None:
            path = self.output_dir / "recording.mp4"
            height, width = frame.shape[:2]
            writer = cv2.VideoWriter(
                str(path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                float(self.display_fps),
                (width, height),
            )
            if writer.isOpened():
                self._video_writer = writer
            else:
                writer.release()
                self._frame_sequence_dir = self.output_dir / "recording_frames"
                self._frame_sequence_dir.mkdir()
                self._event("video_fallback_to_frame_sequence")
        if self._video_writer is not None:
            self._video_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        elif self._frame_sequence_dir is not None:
            path = self._frame_sequence_dir / f"frame_{self._recorded_frames:08d}.png"
            if not cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)):
                raise RuntimeError(f"無法寫入manual frame：{path}")
        self._recorded_frames += 1

    def _scenario_hash(self) -> str:
        payload = {
            "id": self.scenario.scenario_id,
            "name": self.scenario.name,
            "status": self.scenario.validation_status,
            "config": asdict(self.scenario.config),
            "effective_config": asdict(self.env.config),
            "calibration_profile": self.calibration_profile,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def close(self) -> Path:
        if self._closed:
            return self.output_dir
        self._closed = True
        self.ended_at = _utc_now()
        self.input_state.clear()
        self._event("session_ended")
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        self._csv_handle.flush()
        self._csv_handle.close()
        self.env.close()
        module_dir = Path(__file__).resolve().parent
        source_hashes = {
            "physics.py": _sha256(module_dir / "physics.py"),
            "state.py": _sha256(module_dir / "state.py"),
            "manual_test.py": _sha256(Path(__file__).resolve()),
        }
        summary = {
            "schema_version": "manual-simulator-test-session-v1",
            "simulator_version": self.env.config.effective_environment_version,
            "source_commit": _git_head(),
            "source_hashes": source_hashes,
            "scenario": self.scenario.name,
            "scenario_id": self.scenario.scenario_id,
            "scenario_history": self._scenario_history,
            "scenario_config_sha256": self._scenario_hash(),
            "validation_status": self.scenario.validation_status,
            "calibration_profile": self.calibration_profile,
            "seed": self.seed,
            "seed_role": "manual_only",
            "formal_evaluation_allowed": False,
            "display_fps": self.display_fps,
            "control_fps": self.env.config.fps,
            "physics_hz": self.env.config.physics_hz,
            "physics_dt": self.env.config.physics_dt,
            "physics_substeps_per_control": (
                self.env.config.physics_hz / self.env.config.fps
            ),
            "dt": self.env.config.dt,
            "viewport": [self.env.config.width, self.env.config.height],
            "playfield": [
                self.env.config.effective_playfield_left,
                self.env.config.effective_playfield_top,
                self.env.config.effective_playfield_right,
                self.env.config.effective_playfield_bottom,
            ],
            "player_geometry": {
                "width": self.env.config.player_width,
                "height": self.env.config.player_height,
            },
            "platform_geometry": {
                "width": self.env.config.platform_width,
                "height": self.env.config.platform_height,
                "spacing": self.env.config.platform_spacing,
            },
            "control_mapping": {
                "LEFT": ["LEFT", "A"],
                "RIGHT": ["RIGHT", "D"],
                "RELEASE_ALL": "no direction or focus lost",
            },
            "start_time": self.started_at,
            "end_time": self.ended_at,
            "steps": self.total_step_count,
            "terminal_reason": self.terminal_reason,
            "manual_rating": self._ratings[-1] if self._ratings else None,
            "notes": [item["note"] for item in self._ratings if item["note"]],
            "recorded_frames": self._recorded_frames,
            "recording": (
                "recording.mp4"
                if (self.output_dir / "recording.mp4").exists()
                else (
                    "recording_frames/"
                    if self._frame_sequence_dir is not None
                    else None
                )
            ),
            "formal_evidence": False,
            "manual_alignment_only": True,
            "holdout_used": False,
            "game_input_used": False,
            "training_started": False,
        }
        (self.output_dir / "session_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.output_dir / "manual_ratings.json").write_text(
            json.dumps(self._ratings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.output_dir / "events.json").write_text(
            json.dumps(self._events, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.output_dir / "README.md").write_text(
            "# Manual Simulator Test Session\n\n"
            "此session僅供人工手感與debug，不是formal Gate或Alignment PASS。\n\n"
            f"- Scenario：`{self.scenario.scenario_id} {self.scenario.name}`\n"
            f"- Validation：`{self.scenario.validation_status}`\n"
            f"- Seed：`{self.seed}`（manual_only）\n"
            "- `formal_evidence=false`\n"
            "- `manual_alignment_only=true`\n"
            "- 未使用holdout、未操作原版遊戲、未啟動訓練。\n",
            encoding="utf-8",
        )
        return self.output_dir


def _pygame_direction_name(key: int) -> str | None:
    import pygame

    return {
        pygame.K_LEFT: "left",
        pygame.K_a: "a",
        pygame.K_RIGHT: "right",
        pygame.K_d: "d",
    }.get(key)


def _handle_rating_key(
    session: ManualSimulatorSession,
    *,
    key: int,
    unicode_value: str,
) -> None:
    import pygame

    draft = session.rating_draft
    if draft is None:
        return
    rating_keys = {
        pygame.K_1: "very_close",
        pygame.K_2: "close",
        pygame.K_3: "noticeably_different",
        pygame.K_4: "very_different",
        pygame.K_5: "unknown",
    }
    if key in rating_keys:
        draft.rating = rating_keys[key]
        question = CALIBRATION_QUESTIONS[draft.question_index]
        answers = draft.calibration_answers or {}
        answers[question] = draft.rating
        draft.calibration_answers = answers
    elif key == pygame.K_q:
        draft.question_index = (
            draft.question_index + 1
        ) % len(CALIBRATION_QUESTIONS)
    elif key == pygame.K_UP:
        draft.tag_index = (draft.tag_index - 1) % len(RATING_TAGS)
    elif key == pygame.K_DOWN:
        draft.tag_index = (draft.tag_index + 1) % len(RATING_TAGS)
    elif key in {pygame.K_RETURN, pygame.K_KP_ENTER}:
        tag = RATING_TAGS[draft.tag_index]
        selected = draft.selected_tags or set()
        if tag in selected:
            selected.remove(tag)
        else:
            selected.add(tag)
        draft.selected_tags = selected
    elif key == pygame.K_TAB:
        draft.note_entry = not draft.note_entry
    elif draft.note_entry and key == pygame.K_BACKSPACE:
        draft.note = draft.note[:-1]
    elif draft.note_entry and unicode_value and unicode_value.isprintable():
        draft.note = (draft.note + unicode_value)[:500]


def run_manual_viewer(session: ManualSimulatorSession) -> None:
    import pygame

    pygame.init()
    screen = pygame.display.set_mode(
        (session.env.config.width, session.env.config.height)
    )
    pygame.display.set_caption(
        "NS-SHAFT Simulator Manual Test (simulator only)"
    )
    clock = pygame.time.Clock()
    accumulator = 0.0
    running = True
    try:
        while running:
            elapsed = clock.tick(session.display_fps) / 1000.0
            accumulator += min(elapsed, 0.25)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue
                if event.type == pygame.WINDOWFOCUSLOST:
                    session.focus_lost()
                    continue
                if event.type == pygame.WINDOWFOCUSGAINED:
                    session.focus_gained()
                    continue
                if event.type == pygame.KEYUP:
                    direction = _pygame_direction_name(event.key)
                    if direction is not None:
                        session.input_state.key_up(direction)
                    continue
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                if event.key == pygame.K_F3:
                    if session.rating_draft is None:
                        session.begin_rating()
                    else:
                        session.save_rating()
                    continue
                if session.rating_draft is not None:
                    _handle_rating_key(
                        session,
                        key=event.key,
                        unicode_value=getattr(event, "unicode", ""),
                    )
                    continue
                direction = _pygame_direction_name(event.key)
                if direction is not None:
                    session.input_state.key_down(direction)
                elif event.key == pygame.K_r:
                    session.reset_scenario()
                elif event.key == pygame.K_n:
                    session.next_scenario()
                elif event.key == pygame.K_b:
                    session.toggle_calibration_profile()
                elif event.key in {pygame.K_p, pygame.K_SPACE}:
                    session.toggle_pause()
                elif event.key == pygame.K_F1:
                    session.toggle_debug()
                elif event.key == pygame.K_F2:
                    session.toggle_recording()
            if (
                not pygame.key.get_focused()
                and session.input_state.focused
            ):
                session.input_state.focus_lost()
            elif not session.input_state.focused:
                session.input_state.focus_gained()

            while (
                accumulator >= session.env.config.dt
                and not session.paused
                and session.rating_draft is None
            ):
                session.step_once()
                accumulator -= session.env.config.dt
            measured_fps = clock.get_fps()
            frame = session.render_frame(measured_fps=measured_fps)
            session.record_frame(frame)
            surface = pygame.surfarray.make_surface(
                np.transpose(frame, (1, 0, 2))
            )
            screen.blit(surface, (0, 0))
            pygame.display.flip()
    finally:
        session.input_state.clear()
        pygame.display.quit()
        pygame.quit()


def run_headless_smoke(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    seed: int = DEFAULT_MANUAL_SEED,
    steps: int = 6,
) -> dict[str, Any]:
    if steps < 2:
        raise ValueError("headless smoke steps必須至少2。")
    session = ManualSimulatorSession(
        scenario="horizontal_acceleration",
        seed=seed,
        output_root=output_root,
        show_debug=True,
    )
    checks: dict[str, bool] = {}
    try:
        session.input_state.key_down("right")
        session.step_once()
        session.focus_lost()
        checks["focus_loss_releases"] = (
            session.input_state.action is Action.RELEASE_ALL
        )
        session.focus_gained()
        session.toggle_pause()
        pause_on = session.paused
        session.toggle_pause()
        checks["pause_toggles"] = pause_on and not session.paused
        visible = session.show_debug
        session.toggle_debug()
        checks["overlay_toggles"] = session.show_debug != visible
        session.reset_scenario()
        checks["reset_works"] = session.step_count == 0
        original = session.scenario.name
        session.next_scenario()
        checks["scenario_switches"] = session.scenario.name != original
        for _ in range(steps - 1):
            if session.paused:
                break
            session.step_once()
        frame = session.render_frame()
        checks["logging_writes"] = (
            frame.shape
            == (session.env.config.height, session.env.config.width, 3)
        )
    finally:
        output_dir = session.close()
    checks = dict(sorted(checks.items()))
    if not all(checks.values()):
        raise RuntimeError(f"manual headless smoke failed: {checks}")
    return {
        "status": "PASS_HEADLESS_MANUAL_SMOKE",
        "output_dir": str(output_dir.resolve()),
        "checks": checks,
        "holdout_used": False,
        "game_input_used": False,
        "training_started": False,
        "formal_evidence": False,
    }


__all__ = [
    "DEFAULT_MANUAL_SEED",
    "DEFAULT_OUTPUT_ROOT",
    "MANUAL_SEED_MINIMUM",
    "RATING_TAGS",
    "RATING_VALUES",
    "CALIBRATION_QUESTIONS",
    "ManualInputState",
    "ManualScenario",
    "ManualSimulatorSession",
    "build_manual_environment",
    "calibration_profile_config",
    "get_manual_scenario",
    "list_manual_scenarios",
    "run_headless_smoke",
    "run_manual_viewer",
    "validate_manual_seed",
]
