from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import numpy as np

from ..envs.shaft_env import ShaftEnv
from ..input_controller import Action
from .scenarios import configure_normal_healing_landing
from .state import ShaftEnvConfig


MANUAL_CALIBRATION_SEED_START = 901_000
TRACE_FIELDS = (
    "scenario",
    "step",
    "action",
    "x",
    "y",
    "vx",
    "vy",
    "support_floor",
    "deepest_floor",
    "events",
    "terminal_reason",
    "collision_diagnostic",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary(values: Iterable[float]) -> dict[str, float | int | None]:
    array = np.asarray(list(values), dtype=np.float64)
    if not len(array):
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "q25": None,
            "q75": None,
            "min": None,
            "max": None,
        }
    return {
        "count": int(len(array)),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "q25": float(np.percentile(array, 25)),
        "q75": float(np.percentile(array, 75)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def _wide_control_config(config: ShaftEnvConfig) -> ShaftEnvConfig:
    return replace(
        config,
        scroll_speed=0.0,
        platform_width=240.0,
        easy_max_platform_shift=min(config.easy_max_platform_shift, 24.0),
    )


def _stand_on_first(env: ShaftEnv, *, velocity_x: float = 0.0) -> None:
    simulator = env.simulator
    if simulator is None:
        raise RuntimeError("Simulator未reset。")
    platform = min(simulator.platforms, key=lambda item: item.floor_index)
    simulator.supported_floor = platform.floor_index
    simulator.player.body.position = (
        platform.center_x,
        platform.top + simulator.player.height / 2,
    )
    simulator.player.body.velocity = (
        velocity_x,
        simulator.config.scroll_speed,
    )


def _top_setup(env: ShaftEnv) -> None:
    simulator = env.simulator
    if simulator is None:
        raise RuntimeError("Simulator未reset。")
    config = env.config
    simulator.supported_floor = None
    simulator.player.body.position = (
        (config.effective_playfield_left + config.effective_playfield_right)
        / 2,
        config.height
        - (config.effective_top_hazard_bottom + 2.0)
        - simulator.player.height / 2,
    )
    simulator.player.body.velocity = (0.0, 100.0)


def _bottom_setup(env: ShaftEnv) -> None:
    simulator = env.simulator
    if simulator is None:
        raise RuntimeError("Simulator未reset。")
    config = env.config
    simulator.supported_floor = None
    simulator.player.body.position = (
        (config.effective_playfield_left + config.effective_playfield_right)
        / 2,
        config.height
        - (config.effective_playfield_bottom - 2.0)
        - simulator.player.height / 2,
    )
    simulator.player.body.velocity = (0.0, -120.0)


def _trace_row(
    env: ShaftEnv,
    *,
    scenario: str,
    step: int,
    action: Action,
    info: dict[str, Any],
) -> dict[str, Any]:
    simulator = env.simulator
    if simulator is None:
        raise RuntimeError("Simulator未reset。")
    body = simulator.player.body
    return {
        "scenario": scenario,
        "step": step,
        "action": action.name,
        "x": round(float(body.position.x), 9),
        "y": round(float(body.position.y), 9),
        "vx": round(float(body.velocity.x), 9),
        "vy": round(float(body.velocity.y), 9),
        "support_floor": simulator.supported_floor,
        "deepest_floor": simulator.deepest_floor,
        "events": json.dumps(info.get("events", []), separators=(",", ":")),
        "terminal_reason": info.get("terminal_reason"),
        "collision_diagnostic": json.dumps(
            getattr(simulator, "last_collision_diagnostic", None),
            separators=(",", ":"),
            sort_keys=True,
        ),
    }


def _run_trace(
    scenario: str,
    config: ShaftEnvConfig,
    actions: list[Action],
    *,
    setup: str,
    seed: int,
    render_calls_per_step: int = 0,
) -> list[dict[str, Any]]:
    env = ShaftEnv(config=config, render_mode="rgb_array")
    rows: list[dict[str, Any]] = []
    try:
        env.reset(seed=seed)
        simulator = env.simulator
        if simulator is None:
            raise RuntimeError("Simulator未reset。")
        if setup == "stand":
            _stand_on_first(env)
        elif setup == "release":
            _stand_on_first(env, velocity_x=160.0)
        elif setup == "reverse":
            _stand_on_first(
                env,
                velocity_x=config.max_horizontal_speed,
            )
        elif setup == "edge":
            _stand_on_first(env)
        elif setup == "landing":
            configure_normal_healing_landing(
                simulator,
                health_segments=simulator.health_segments,
                fall_speed=-180.0,
            )
        elif setup == "top":
            _top_setup(env)
        elif setup == "bottom":
            _bottom_setup(env)
        else:
            raise ValueError(f"未知trace setup：{setup}")
        for step, action in enumerate(actions, start=1):
            for _ in range(render_calls_per_step):
                env.render()
            _observation, _reward, terminated, truncated, info = env.step(
                int(action)
            )
            rows.append(
                _trace_row(
                    env,
                    scenario=scenario,
                    step=step,
                    action=action,
                    info=info,
                )
            )
            if terminated or truncated:
                break
        return rows
    finally:
        env.close()


def calibration_traces(
    config: ShaftEnvConfig,
) -> dict[str, list[dict[str, Any]]]:
    control = _wide_control_config(config)
    return {
        "M02_acceleration": _run_trace(
            "M02_acceleration",
            control,
            [Action.RIGHT] * 10 + [Action.RELEASE_ALL] * 5,
            setup="stand",
            seed=MANUAL_CALIBRATION_SEED_START,
        ),
        "M03_release": _run_trace(
            "M03_release",
            control,
            [Action.RELEASE_ALL] * 10,
            setup="release",
            seed=MANUAL_CALIBRATION_SEED_START + 1,
        ),
        "M04_reverse": _run_trace(
            "M04_reverse",
            control,
            [Action.LEFT] * 10,
            setup="reverse",
            seed=MANUAL_CALIBRATION_SEED_START + 2,
        ),
        "M05_edge": _run_trace(
            "M05_edge",
            replace(control, platform_width=200.0),
            [Action.RIGHT] * 20,
            setup="edge",
            seed=MANUAL_CALIBRATION_SEED_START + 3,
        ),
        "M06_landing": _run_trace(
            "M06_landing",
            config,
            [Action.RELEASE_ALL] * 20,
            setup="landing",
            seed=MANUAL_CALIBRATION_SEED_START + 4,
        ),
        "M07_top": _run_trace(
            "M07_top",
            replace(config, scroll_speed=0.0),
            [Action.RELEASE_ALL] * 10,
            setup="top",
            seed=MANUAL_CALIBRATION_SEED_START + 5,
        ),
        "M08_bottom": _run_trace(
            "M08_bottom",
            replace(config, scroll_speed=0.0),
            [Action.RELEASE_ALL] * 10,
            setup="bottom",
            seed=MANUAL_CALIBRATION_SEED_START + 6,
        ),
    }


def layout_distribution(
    config: ShaftEnvConfig,
    *,
    seed_count: int = 100,
) -> dict[str, Any]:
    visible_counts: list[float] = []
    vertical_gaps: list[float] = []
    horizontal_shifts: list[float] = []
    widths: list[float] = []
    trivial = 0
    impossible = 0
    patterns: list[list[float]] = []
    for offset in range(seed_count):
        env = ShaftEnv(config=config)
        try:
            env.reset(seed=MANUAL_CALIBRATION_SEED_START + 100 + offset)
            simulator = env.simulator
            if simulator is None:
                raise RuntimeError("Simulator未reset。")
            ordered = sorted(
                simulator.platforms,
                key=lambda item: item.floor_index,
            )
            visible_counts.append(
                float(
                    sum(
                        -item.height
                        <= config.height - item.top
                        <= config.height + item.height
                        for item in ordered
                    )
                )
            )
            shifts: list[float] = []
            for source, target in zip(ordered, ordered[1:]):
                vertical_gaps.append(abs(target.center_y - source.center_y))
                shift = abs(target.center_x - source.center_x)
                shifts.append(float(shift))
                horizontal_shifts.append(float(shift))
                widths.append(float(source.width))
                if shift < 12.0:
                    trivial += 1
                max_reachable = (
                    config.max_horizontal_speed
                    * max(0.1, config.platform_spacing / max(config.scroll_speed, 1.0))
                    + config.platform_width
                )
                if shift > max_reachable:
                    impossible += 1
            widths.append(float(ordered[-1].width))
            patterns.append(shifts[:10])
        finally:
            env.close()
    return {
        "seed_range": [
            MANUAL_CALIBRATION_SEED_START + 100,
            MANUAL_CALIBRATION_SEED_START + 99 + seed_count,
        ],
        "seed_role": "manual_only",
        "formal_evaluation_allowed": False,
        "visible_platform_count_initial": _summary(visible_counts),
        "vertical_gap": _summary(vertical_gaps),
        "absolute_horizontal_center_shift": _summary(horizontal_shifts),
        "platform_width": _summary(widths),
        "trivial_transition_count_shift_below_12": trivial,
        "impossible_transition_count_conservative": impossible,
        "first_three_seed_patterns": patterns[:3],
        "reproducible": True,
    }


def fps_invariance(config: ShaftEnvConfig) -> dict[str, Any]:
    actions = [Action.RELEASE_ALL] * 12
    results: dict[str, Any] = {}
    for render_fps in (30, 60, 120):
        rows = _run_trace(
            "M06_fps_invariance",
            config,
            actions,
            setup="landing",
            seed=MANUAL_CALIBRATION_SEED_START + 500,
            render_calls_per_step=render_fps // config.fps,
        )
        results[str(render_fps)] = {
            "render_fps": render_fps,
            "control_steps": len(rows),
            "physics_steps": len(rows) * config.physics_hz // config.fps,
            "final": rows[-1],
            "landing_steps": [
                row["step"] for row in rows if "landed" in row["events"]
            ],
        }
    canonical = results["60"]
    passed = all(
        item["control_steps"] == canonical["control_steps"]
        and item["physics_steps"] == canonical["physics_steps"]
        and item["landing_steps"] == canonical["landing_steps"]
        and item["final"] == canonical["final"]
        for item in results.values()
    )
    return {
        "passed": passed,
        "interpretation": (
            "render calls are read-only; fixed 60 Hz physics is batched behind 10 Hz control"
        ),
        "results": results,
    }


def _collision_case(
    config: ShaftEnvConfig,
    *,
    name: str,
    player_x_offset_from_platform_right: float,
    velocity: tuple[float, float],
    bottom_gap: float,
    action: Action,
    scroll_speed: float = 0.0,
) -> dict[str, Any]:
    env = ShaftEnv(config=replace(config, scroll_speed=scroll_speed))
    try:
        env.reset(seed=MANUAL_CALIBRATION_SEED_START + 600)
        simulator = env.simulator
        if simulator is None:
            raise RuntimeError("Simulator未reset。")
        platform = min(simulator.platforms, key=lambda item: item.floor_index)
        simulator.supported_floor = None
        simulator.player.body.position = (
            platform.right
            + player_x_offset_from_platform_right,
            platform.top + simulator.player.height / 2 + bottom_gap,
        )
        simulator.player.body.velocity = velocity
        before = {
            "player_position": list(map(float, simulator.player.body.position)),
            "player_velocity": list(map(float, simulator.player.body.velocity)),
            "platform_bbox": [
                float(platform.left),
                float(platform.top),
                float(platform.right),
                float(platform.top + platform.height),
            ],
        }
        _observation, _reward, terminated, _truncated, info = env.step(int(action))
        return {
            "case": name,
            "before": before,
            "after": {
                "player_position": list(map(float, simulator.player.body.position)),
                "player_velocity": list(map(float, simulator.player.body.velocity)),
                "support_floor": simulator.supported_floor,
                "events": info["events"],
                "terminal_reason": info["terminal_reason"],
                "terminated": terminated,
                "diagnostic": getattr(
                    simulator,
                    "last_collision_diagnostic",
                    None,
                ),
            },
            "landed": "landed" in info["events"],
        }
    finally:
        env.close()


def collision_diagnostics(config: ShaftEnvConfig) -> dict[str, Any]:
    half_width = config.player_width / 2
    cases = {
        "downward_center": _collision_case(
            config,
            name="downward_center",
            player_x_offset_from_platform_right=-config.platform_width / 2,
            velocity=(0.0, -1500.0),
            bottom_gap=8.0,
            action=Action.RELEASE_ALL,
        ),
        "diagonal_edge": _collision_case(
            config,
            name="diagonal_edge",
            player_x_offset_from_platform_right=half_width - 3.5,
            velocity=(config.max_horizontal_speed, -240.0),
            bottom_gap=1.0,
            action=Action.RIGHT,
        ),
        "moving_platform_relative": _collision_case(
            config,
            name="moving_platform_relative",
            player_x_offset_from_platform_right=-config.platform_width / 2,
            velocity=(0.0, 0.0),
            bottom_gap=1.0,
            action=Action.RELEASE_ALL,
            scroll_speed=config.scroll_speed,
        ),
        "rising_from_below": _collision_case(
            config,
            name="rising_from_below",
            player_x_offset_from_platform_right=-config.platform_width / 2,
            velocity=(0.0, 300.0),
            bottom_gap=-8.0,
            action=Action.RELEASE_ALL,
        ),
    }
    return {
        "cases": cases,
        "downward_tunneling_detected": not cases["downward_center"]["landed"],
        "diagonal_edge_tunneling_detected": not cases["diagonal_edge"]["landed"],
        "moving_platform_missed": not cases["moving_platform_relative"]["landed"],
        "rising_from_below_landed": cases["rising_from_below"]["landed"],
        "one_way_semantics": "UNRESOLVED_ONE_WAY_SEMANTICS",
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_velocity_svg(
    path: Path,
    traces: dict[str, list[dict[str, Any]]],
    *,
    title: str,
) -> None:
    width, height = 900, 420
    margin = 50
    selected = {
        key: traces[key]
        for key in ("M02_acceleration", "M03_release", "M04_reverse")
    }
    values = [float(row["vx"]) for rows in selected.values() for row in rows]
    limit = max(1.0, max(abs(value) for value in values))
    colors = {
        "M02_acceleration": "#2f81f7",
        "M03_release": "#3fb950",
        "M04_reverse": "#f85149",
    }
    paths = []
    legends = []
    for index, (name, rows) in enumerate(selected.items()):
        points = []
        for row in rows:
            x = margin + (float(row["step"]) - 1) / 14 * (width - 2 * margin)
            y = height / 2 - float(row["vx"]) / limit * (height / 2 - margin)
            points.append(f"{x:.2f},{y:.2f}")
        paths.append(
            f'<polyline fill="none" stroke="{colors[name]}" stroke-width="2" points="{" ".join(points)}" />'
        )
        legends.append(
            f'<text x="{margin + index * 240}" y="{height - 12}" fill="{colors[name]}">{name}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        '<rect width="100%" height="100%" fill="#0d1117" />'
        f'<text x="{margin}" y="28" fill="#f0f6fc" font-size="18">{title}</text>'
        f'<line x1="{margin}" y1="{height / 2}" x2="{width - margin}" y2="{height / 2}" stroke="#8b949e" />'
        + "".join(paths)
        + "".join(legends)
        + "</svg>\n"
    )
    path.write_text(svg, encoding="utf-8")


def capture_calibration_profile(
    *,
    output_dir: Path,
    label: str,
    config: ShaftEnvConfig | None = None,
) -> dict[str, Any]:
    profile = config or ShaftEnvConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    traces = calibration_traces(profile)
    for name, rows in traces.items():
        _write_csv(output_dir / f"{name}_trajectory.csv", rows)
    _write_velocity_svg(
        output_dir / "acceleration_velocity.svg",
        traces,
        title=f"Manual simulator calibration: {label}",
    )
    acceleration = traces["M02_acceleration"]
    release = traces["M03_release"]
    reverse = traces["M04_reverse"]
    stop_steps = [row["step"] for row in reverse if float(row["vx"]) <= 0]
    left_steps = [row["step"] for row in reverse if float(row["vx"]) < 0]
    metrics = {
        "schema_version": "manual-simulator-calibration-profile-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "label": label,
        "formal_evidence": False,
        "manual_alignment_only": True,
        "seed_role": "manual_only",
        "formal_evaluation_allowed": False,
        "simulator_version": profile.effective_environment_version,
        "config": asdict(profile),
        "control": {
            "horizontal_acceleration": profile.horizontal_acceleration,
            "air_control_multiplier": getattr(profile, "air_control_multiplier", 1.0),
            "max_horizontal_speed": profile.max_horizontal_speed,
            "release_drag": profile.release_drag,
            "release_deceleration": getattr(profile, "release_deceleration", None),
            "reverse_brake_multiplier": getattr(profile, "reverse_brake_multiplier", 1.0),
            "gravity": profile.gravity,
            "max_fall_speed": getattr(profile, "max_fall_speed", None),
            "supported_right_delta_vx_first_step": float(acceleration[0]["vx"]),
            "release_speed_after_one_step_from_160": abs(float(release[0]["vx"])),
            "reverse_stop_step_from_max_right": min(stop_steps) if stop_steps else None,
            "reverse_leftward_step_from_max_right": min(left_steps) if left_steps else None,
        },
        "timing": {
            "control_fps": profile.fps,
            "control_dt": profile.dt,
            "physics_hz": profile.physics_hz,
            "physics_dt": profile.physics_dt,
            "substeps_per_control_step": profile.physics_hz / profile.fps,
            "render_fps_diagnostic": [30, 60, 120],
        },
        "scroll": {
            "pixels_per_second": profile.scroll_speed,
            "platform_heights_per_second": profile.scroll_speed / profile.platform_height,
        },
        "layout": layout_distribution(profile),
        "fps_invariance": fps_invariance(profile),
        "collision": collision_diagnostics(profile),
        "real_reference": {
            "source": "artifacts/simulator_real_alignment_audit_v3.json and primary alignment packet",
            "cadence_ms_median": 125.0,
            "left_delta_vx_median": -44.0,
            "right_delta_vx_median": 63.272727,
            "release_speed_ratio_median_abs_vx_ge_40": 0.26,
            "absolute_player_vx_median": 128.0,
            "absolute_player_vx_q75": 172.0,
            "visible_platform_count_median": 7.0,
            "vertical_top_gap_median": 48.0,
            "absolute_horizontal_center_shift_median": 80.0,
            "platform_width_median": 95.0,
            "measured_scroll_pixels_per_second": 96.0,
            "user_reports_scroll_subjectively_too_fast": True,
        },
        "source_hashes": {
            "state.py": _sha256(Path(__file__).with_name("state.py")),
            "physics.py": _sha256(Path(__file__).with_name("physics.py")),
            "generator.py": _sha256(Path(__file__).with_name("generator.py")),
            "manual_test.py": _sha256(Path(__file__).with_name("manual_test.py")),
            "calibration_review.py": _sha256(Path(__file__)),
        },
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metrics


def write_calibration_comparison(
    *,
    before_path: Path,
    after_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = {
        "horizontal_acceleration": (
            before["control"]["horizontal_acceleration"],
            after["control"]["horizontal_acceleration"],
        ),
        "air_control_multiplier": (
            before["control"]["air_control_multiplier"],
            after["control"]["air_control_multiplier"],
        ),
        "max_horizontal_speed": (
            before["control"]["max_horizontal_speed"],
            after["control"]["max_horizontal_speed"],
        ),
        "release_speed_after_one_step_from_160": (
            before["control"]["release_speed_after_one_step_from_160"],
            after["control"]["release_speed_after_one_step_from_160"],
        ),
        "reverse_leftward_step_from_max_right": (
            before["control"]["reverse_leftward_step_from_max_right"],
            after["control"]["reverse_leftward_step_from_max_right"],
        ),
        "scroll_speed": (
            before["scroll"]["pixels_per_second"],
            after["scroll"]["pixels_per_second"],
        ),
        "vertical_gap_median": (
            before["layout"]["vertical_gap"]["median"],
            after["layout"]["vertical_gap"]["median"],
        ),
        "horizontal_shift_median": (
            before["layout"]["absolute_horizontal_center_shift"]["median"],
            after["layout"]["absolute_horizontal_center_shift"]["median"],
        ),
        "diagonal_edge_tunneling_detected": (
            before["collision"]["diagonal_edge_tunneling_detected"],
            after["collision"]["diagonal_edge_tunneling_detected"],
        ),
    }
    comparison = {
        "schema_version": "manual-simulator-calibration-comparison-v1",
        "formal_evidence": False,
        "manual_alignment_only": True,
        "before": str(before_path.as_posix()),
        "after": str(after_path.as_posix()),
        "changes": {
            key: {"before": values[0], "after": values[1]}
            for key, values in fields.items()
        },
        "fps_invariance_before": before["fps_invariance"]["passed"],
        "fps_invariance_after": after["fps_invariance"]["passed"],
        "one_way_semantics": "UNRESOLVED_ONE_WAY_SEMANTICS",
        "needs_more_real_reference": [
            "subjective scroll-speed preference conflicts with measured 96 px/s",
            "rising-from-below one-way behavior needs direct real-game clip",
            "layout statistics need a longer unobstructed real free-play clip",
        ],
    }
    (output_dir / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return comparison


__all__ = [
    "MANUAL_CALIBRATION_SEED_START",
    "calibration_traces",
    "capture_calibration_profile",
    "collision_diagnostics",
    "fps_invariance",
    "layout_distribution",
    "write_calibration_comparison",
]
