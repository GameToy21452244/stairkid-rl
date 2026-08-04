"""Render the frozen spring failure seed before and after Oracle repair."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.training.spring_curriculum_gate import spring_curriculum_config


@dataclass(frozen=True)
class Rollout:
    label: str
    frames: tuple[np.ndarray, ...]
    steps: int
    deepest_floor: int
    outcome: str
    event_counts: dict[str, int]
    spring_contact_steps: tuple[int, ...]


def _put_text(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    *,
    scale: float = 0.48,
    color: tuple[int, int, int] = (235, 235, 235),
) -> None:
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


def _panel(
    rgb_frame: np.ndarray,
    *,
    label: str,
    step: int,
    floor: int,
    action: str,
    events: tuple[str, ...],
    status: str,
) -> np.ndarray:
    height, width = rgb_frame.shape[:2]
    panel = np.full((height + 72, width, 3), 18, dtype=np.uint8)
    panel[72:] = rgb_frame
    title_color = (235, 100, 100) if label == "LEGACY" else (90, 225, 125)
    _put_text(panel, label, (10, 20), scale=0.62, color=title_color)
    _put_text(
        panel,
        f"step={step:03d}  floor={floor:02d}  action={action}  status={status}",
        (10, 42),
    )
    event_text = ",".join(events) if events else "-"
    _put_text(panel, f"events={event_text}", (10, 63), scale=0.43)
    return panel


def _rollout(
    *,
    seed: int,
    label: str,
    spring_escape: bool,
    max_steps: int,
    target_floor: int,
) -> Rollout:
    env = ShaftEnv(config=spring_curriculum_config(), render_mode="rgb_array")
    oracle = OracleFull(enable_spring_escape=spring_escape)
    event_counts: Counter[str] = Counter()
    frames: list[np.ndarray] = []
    spring_contact_steps: list[int] = []
    outcome = "max_steps"
    step = 0
    try:
        env.reset(seed=seed)
        for step in range(1, max_steps + 1):
            decision = oracle.choose(env.simulator)
            _, _, terminated, truncated, info = env.step(int(decision.action))
            events = tuple(str(event) for event in info["events"])
            event_counts.update(events)
            if "spring_contact" in events:
                spring_contact_steps.append(step)
            floor = int(env.simulator.deepest_floor)
            if floor >= target_floor:
                outcome = "target_reached"
            elif terminated or truncated:
                outcome = str(info["terminal_reason"])
            else:
                outcome = "running"
            rendered = env.render()
            if rendered is None:
                raise RuntimeError("rgb_array renderer unexpectedly returned None")
            frames.append(
                _panel(
                    rendered,
                    label=label,
                    step=step,
                    floor=floor,
                    action=decision.action.name,
                    events=events,
                    status=outcome,
                )
            )
            if outcome != "running":
                break
        if outcome == "running":
            outcome = "max_steps"
        for _ in range(10):
            frames.append(frames[-1].copy())
        return Rollout(
            label=label,
            frames=tuple(frames),
            steps=step,
            deepest_floor=int(env.simulator.deepest_floor),
            outcome=outcome,
            event_counts=dict(sorted(event_counts.items())),
            spring_contact_steps=tuple(spring_contact_steps),
        )
    finally:
        env.close()


def _write_mp4(path: Path, frames: tuple[np.ndarray, ...], fps: float) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing video: {path}")
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
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


def _pad_frames(
    frames: tuple[np.ndarray, ...],
    length: int,
) -> tuple[np.ndarray, ...]:
    return frames + (frames[-1],) * (length - len(frames))


def _contact_montage(legacy: Rollout, fixed: Rollout) -> np.ndarray:
    selected: list[np.ndarray] = []
    for rollout in (legacy, fixed):
        if rollout.spring_contact_steps:
            contact = rollout.spring_contact_steps[0] - 1
        else:
            contact = 0
        indices = [
            max(0, min(len(rollout.frames) - 1, contact + offset))
            for offset in (0, 2, 5)
        ]
        selected.append(np.concatenate([rollout.frames[index] for index in indices], axis=1))
    return np.concatenate(selected, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=10007)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--target-floor", type=int, default=10)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts") / "simulator_visuals",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    legacy = _rollout(
        seed=args.seed,
        label="LEGACY",
        spring_escape=False,
        max_steps=args.max_steps,
        target_floor=args.target_floor,
    )
    fixed = _rollout(
        seed=args.seed,
        label="FIXED",
        spring_escape=True,
        max_steps=args.max_steps,
        target_floor=args.target_floor,
    )
    stem = f"spring_oracle_seed_{args.seed}"
    legacy_path = args.output_dir / f"{stem}_legacy.mp4"
    fixed_path = args.output_dir / f"{stem}_fixed.mp4"
    comparison_path = args.output_dir / f"{stem}_comparison.mp4"
    montage_path = args.output_dir / f"{stem}_contact_montage.png"
    manifest_path = args.output_dir / f"{stem}_manifest.json"
    for path in (
        legacy_path,
        fixed_path,
        comparison_path,
        montage_path,
        manifest_path,
    ):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    _write_mp4(legacy_path, legacy.frames, fps=10.0)
    _write_mp4(fixed_path, fixed.frames, fps=10.0)
    length = max(len(legacy.frames), len(fixed.frames))
    legacy_frames = _pad_frames(legacy.frames, length)
    fixed_frames = _pad_frames(fixed.frames, length)
    comparison_frames = tuple(
        np.concatenate([left, right], axis=1)
        for left, right in zip(legacy_frames, fixed_frames, strict=True)
    )
    _write_mp4(comparison_path, comparison_frames, fps=10.0)
    montage = _contact_montage(legacy, fixed)
    if not cv2.imwrite(str(montage_path), cv2.cvtColor(montage, cv2.COLOR_RGB2BGR)):
        raise RuntimeError(f"Unable to create montage: {montage_path}")

    manifest = {
        "purpose": "same-seed visual comparison of legacy and repaired Oracle spring control",
        "seed": args.seed,
        "target_floor": args.target_floor,
        "max_steps": args.max_steps,
        "color_legend": {
            "player": "yellow",
            "normal_platform": "green",
            "spikes": "red",
            "spring": "orange",
        },
        "legacy": {
            "spring_escape_enabled": False,
            "steps": legacy.steps,
            "deepest_floor": legacy.deepest_floor,
            "outcome": legacy.outcome,
            "event_counts": legacy.event_counts,
            "spring_contact_steps": list(legacy.spring_contact_steps),
            "video": legacy_path.as_posix(),
        },
        "fixed": {
            "spring_escape_enabled": True,
            "steps": fixed.steps,
            "deepest_floor": fixed.deepest_floor,
            "outcome": fixed.outcome,
            "event_counts": fixed.event_counts,
            "spring_contact_steps": list(fixed.spring_contact_steps),
            "video": fixed_path.as_posix(),
        },
        "comparison_video": comparison_path.as_posix(),
        "contact_montage": montage_path.as_posix(),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
