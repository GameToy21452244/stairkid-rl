"""Render legacy, calibrated Simulator v0.3, and real edge departures."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np

import _common  # noqa: F401,E402

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.training.simulator_v03_edge_gate import edge_fidelity_config


OUTPUT_DIR = Path("artifacts") / "simulator_visuals"
REAL_DIR = Path("logs") / "teacher_real_micro_20260803_205952_924961"
REAL_VIDEO = REAL_DIR / "episode_03.mp4"
REAL_ALIGNMENT = REAL_DIR / "episode_03.alignment.jsonl"
SEED = 10007
FPS = 8.0
PANEL_HEIGHT = 74
FRAME_HEIGHT = 430


@dataclass(frozen=True)
class Rollout:
    label: str
    frames: tuple[np.ndarray, ...]
    raw_frames: tuple[np.ndarray, ...]
    events: tuple[tuple[str, ...], ...]
    deepest_floor: int
    outcome: str
    event_counts: dict[str, int]
    departure_frame: int | None
    first_landing_frame: int | None


def _text(
    frame: np.ndarray,
    value: str,
    origin: tuple[int, int],
    *,
    color: tuple[int, int, int] = (235, 235, 235),
    scale: float = 0.46,
) -> None:
    cv2.putText(
        frame,
        value,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        1,
        cv2.LINE_AA,
    )


def _normalize_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.resize(frame, (634, FRAME_HEIGHT), interpolation=cv2.INTER_AREA)


def _panel(
    frame: np.ndarray,
    *,
    title: str,
    line_one: str,
    line_two: str,
    color: tuple[int, int, int],
) -> np.ndarray:
    normalized = _normalize_rgb(frame)
    panel = np.full(
        (FRAME_HEIGHT + PANEL_HEIGHT, normalized.shape[1], 3),
        16,
        dtype=np.uint8,
    )
    panel[PANEL_HEIGHT:] = normalized
    _text(panel, title, (10, 21), color=color, scale=0.60)
    _text(panel, line_one, (10, 44))
    _text(panel, line_two, (10, 65), scale=0.42)
    return panel


def _write_mp4(path: Path, frames: tuple[np.ndarray, ...]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (width, height),
    )
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(f"Unable to create MP4: {path}")
    try:
        for frame in frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()


def _rollout(label: str, *, legacy: bool) -> Rollout:
    config = edge_fidelity_config()
    if legacy:
        config = replace(
            config,
            environment_version="ns-shaft-sim-v0.2",
            enable_support_ownership=False,
            enable_calibrated_playfield=False,
        )
    env = ShaftEnv(config=config, render_mode="rgb_array")
    oracle = OracleFull()
    panels: list[np.ndarray] = []
    raw_frames: list[np.ndarray] = []
    event_rows: list[tuple[str, ...]] = []
    counts: Counter[str] = Counter()
    departure_frame = None
    first_landing_frame = None
    outcome = "max_steps"
    try:
        env.reset(seed=SEED)
        for step in range(1, 61):
            decision = oracle.choose(env.simulator)
            _, _, terminated, truncated, info = env.step(int(decision.action))
            events = tuple(str(event) for event in info["events"])
            counts.update(events)
            if departure_frame is None and "support_departed" in events:
                departure_frame = len(panels)
            if first_landing_frame is None and "floor_descended" in events:
                first_landing_frame = len(panels)
            rendered = env.renderer.rgb_array(env.simulator, None)
            raw_frames.append(_normalize_rgb(rendered))
            panels.append(
                _panel(
                    rendered,
                    title=label,
                    line_one=(
                        f"seed={SEED} step={step:02d} floor="
                        f"{env.simulator.deepest_floor} action={decision.action.name}"
                    ),
                    line_two=(
                        f"support={env.simulator.supported_floor} "
                        f"events={','.join(events) if events else '-'}"
                    ),
                    color=(225, 95, 95) if legacy else (80, 225, 125),
                )
            )
            event_rows.append(events)
            if env.simulator.deepest_floor >= 2:
                outcome = "floor_2_reached"
                break
            if terminated or truncated:
                outcome = str(info["terminal_reason"])
                break
        return Rollout(
            label=label,
            frames=tuple(panels),
            raw_frames=tuple(raw_frames),
            events=tuple(event_rows),
            deepest_floor=int(env.simulator.deepest_floor),
            outcome=outcome,
            event_counts=dict(sorted(counts.items())),
            departure_frame=departure_frame,
            first_landing_frame=first_landing_frame,
        )
    finally:
        env.close()


def _read_real_rows() -> dict[int, dict[str, object]]:
    rows = {}
    for line in REAL_ALIGNMENT.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[int(row["decision_frame_index"])] = row
    return rows


def _real_clip() -> tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]:
    rows = _read_real_rows()
    capture = cv2.VideoCapture(str(REAL_VIDEO))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Unable to read real video: {REAL_VIDEO}")
    panels: list[np.ndarray] = []
    raw_frames: list[np.ndarray] = []
    try:
        for frame_index in range(33, 41):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, bgr = capture.read()
            if not ok:
                raise RuntimeError(f"Unable to read real frame {frame_index}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            raw_frames.append(_normalize_rgb(rgb))
            row = rows[frame_index]
            observation = row["observation"]
            player = observation["player"]
            memory = row["pre_decision_memory"]
            panels.append(
                _panel(
                    rgb,
                    title="REAL GAME / episode 03",
                    line_one=(
                        f"frame={frame_index} x={player['center_x']:.1f} "
                        f"y={player['center_y']:.1f} "
                        f"action={row['teacher']['action_name']}"
                    ),
                    line_two=(
                        f"support={memory['support_platform_id']} "
                        f"target={memory['target_platform_id']} "
                        f"phase={memory['controller_phase']}"
                    ),
                    color=(95, 185, 245),
                )
            )
    finally:
        capture.release()
    return tuple(panels), tuple(raw_frames)


def _semantic_clip(rollout: Rollout, length: int) -> tuple[np.ndarray, ...]:
    departure = rollout.departure_frame or 0
    landing = rollout.first_landing_frame or len(rollout.frames) - 1
    start = max(0, departure - 3)
    stop = min(len(rollout.frames), landing + 2)
    selected = list(rollout.frames[start:stop])
    if not selected:
        selected = [rollout.frames[0]]
    while len(selected) < length:
        selected.append(selected[-1].copy())
    return tuple(selected[:length])


def _pad(
    frames: tuple[np.ndarray, ...], length: int
) -> tuple[np.ndarray, ...]:
    return frames + (frames[-1],) * (length - len(frames))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "legacy": OUTPUT_DIR / "simulator_v02_seed_10007_pass_through.mp4",
        "current": OUTPUT_DIR / "simulator_v03_seed_10007_edge_departure.mp4",
        "legacy_vs_current": OUTPUT_DIR
        / "simulator_v02_vs_v03_edge_comparison.mp4",
        "real": OUTPUT_DIR / "real_episode3_frames33_40_edge_departure.mp4",
        "real_vs_current": OUTPUT_DIR
        / "real_vs_simulator_v03_edge_departure.mp4",
        "montage": OUTPUT_DIR / "real_vs_simulator_v03_edge_montage.png",
        "manifest": OUTPUT_DIR / "real_vs_simulator_v03_edge_manifest.json",
    }
    for path in outputs.values():
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    legacy = _rollout("LEGACY v0.2 / INVALID", legacy=True)
    current = _rollout("SIMULATOR v0.3 / CALIBRATED", legacy=False)
    real_panels, real_raw = _real_clip()
    _write_mp4(outputs["legacy"], legacy.frames)
    _write_mp4(outputs["current"], current.frames)
    comparison_length = max(len(legacy.frames), len(current.frames))
    _write_mp4(
        outputs["legacy_vs_current"],
        tuple(
            np.concatenate((left, right), axis=1)
            for left, right in zip(
                _pad(legacy.frames, comparison_length),
                _pad(current.frames, comparison_length),
                strict=True,
            )
        ),
    )
    _write_mp4(outputs["real"], real_panels)
    current_semantic = _semantic_clip(current, len(real_panels))
    _write_mp4(
        outputs["real_vs_current"],
        tuple(
            np.concatenate((real, simulator), axis=1)
            for real, simulator in zip(
                real_panels, current_semantic, strict=True
            )
        ),
    )

    departure = current.departure_frame or 0
    landing = current.first_landing_frame or len(current.raw_frames) - 1
    simulator_indices = (0, max(0, departure - 1), departure, landing)
    real_indices = (0, 3, 4, 6)
    real_row = np.concatenate(
        tuple(real_raw[index] for index in real_indices), axis=1
    )
    simulator_row = np.concatenate(
        tuple(current.raw_frames[index] for index in simulator_indices),
        axis=1,
    )
    montage = np.concatenate((real_row, simulator_row), axis=0)
    if not cv2.imwrite(
        str(outputs["montage"]), cv2.cvtColor(montage, cv2.COLOR_RGB2BGR)
    ):
        raise RuntimeError(f"Unable to write montage: {outputs['montage']}")

    manifest = {
        "schema_version": "simulator-real-edge-visual-comparison-v1",
        "semantic_comparison_not_time_synchronized": True,
        "one_to_one_claimed": False,
        "real_reference": {
            "video": REAL_VIDEO.as_posix(),
            "alignment": REAL_ALIGNMENT.as_posix(),
            "episode": 3,
            "frames": [33, 40],
            "capture_size": [634, 430],
            "observed_platform_edge_bounds_x": [40, 423],
            "observed_platform_top_range_y": [68, 400],
            "observed_scroll_speed_pixels_per_second": 96,
        },
        "simulator_v03": {
            "seed": SEED,
            "environment_version": "ns-shaft-sim-v0.3",
            "canvas_size": [634, 431],
            "playfield_bounds": [40, 60, 423, 416],
            "top_hazard_bottom": 88,
            "initial_player_center_screen": [231.5, 338.5],
            "departure_frame": current.departure_frame,
            "first_landing_frame": current.first_landing_frame,
            "deepest_floor": current.deepest_floor,
            "outcome": current.outcome,
            "event_counts": current.event_counts,
        },
        "legacy_v02": {
            "invalid_for_real_fidelity": True,
            "reason": "full-canvas playfield and no support ownership",
            "deepest_floor": legacy.deepest_floor,
            "outcome": legacy.outcome,
            "event_counts": legacy.event_counts,
        },
        "remaining_unvalidated": [
            "pixel-perfect character and platform collision masks",
            "special-platform dynamics under calibrated playfield",
            "detector noise and missed detections",
            "long-horizon top-pressure success",
        ],
        "outputs": {key: value.as_posix() for key, value in outputs.items()},
    }
    outputs["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
