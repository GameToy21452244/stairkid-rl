"""Supervised Real detector calibration; capture only, never keyboard input."""

from __future__ import annotations

import argparse
from pathlib import Path
import time

import cv2

from stair_agent.config import AppConfig
from stair_agent.diagnostics import save_image
from stair_agent.screen_capture import ScreenCapture
from stair_agent.window_manager import WindowManager


KINDS = (
    "dialog",
    "normal",
    "spikes",
    "spring",
    "conveyor-1",
    "conveyor-2",
    "flipping-1",
    "flipping-2",
)


def _select_roi(title: str, frame, instruction: str) -> tuple[int, int, int, int]:
    print(instruction)
    left, top, width, height = (
        int(value) for value in cv2.selectROI(title, frame, showCrosshair=True)
    )
    cv2.destroyWindow(title)
    if width <= 0 or height <= 0:
        raise RuntimeError("CALIBRATION_ROI_CANCELLED")
    return left, top, width, height


def capture_visible_client(project_root: Path, config: AppConfig):
    """Focus and capture the configured client without constructing a controller."""

    manager = WindowManager()
    target = manager.require_ready(
        config.game.window_title_contains,
        config.game.window_class_name,
    )
    manager.focus(target.hwnd)
    time.sleep(1.0)
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        return capture.capture()


def calibrate_kind(project_root: Path, kind: str) -> Path:
    root = Path(project_root).resolve()
    if kind not in KINDS:
        raise ValueError(f"CALIBRATION_KIND_INVALID:{kind}")
    config_path = root / "config.yaml"
    config = AppConfig.load(config_path)
    print("The game window will be focused for one passive screenshot.")
    print("No game key or policy action is sent by this calibration tool.")
    frame = capture_visible_client(root, config)

    if kind == "dialog":
        box = _select_roi(
            "StairKid dialog calibration",
            frame,
            "Select the complete central white menu/game-over dialog, then press Enter.",
        )
        left, top, width, height = box
        config.detection.dialog_roi_left = left
        config.detection.dialog_roi_top = top
        config.detection.dialog_roi_width = width
        config.detection.dialog_roi_height = height
        config.detection.reference_width = int(frame.shape[1])
        config.detection.reference_height = int(frame.shape[0])
        relative = Path(config.detection.dialog_template_path)
    else:
        if kind == "normal":
            playfield = _select_roi(
                "StairKid playfield calibration",
                frame,
                "Select only the blue playable shaft area (exclude HUD/buttons).",
            )
            (
                config.vision.playfield_left,
                config.vision.playfield_top,
                config.vision.playfield_width,
                config.vision.playfield_height,
            ) = playfield
            config.vision.reference_width = int(frame.shape[1])
            config.vision.reference_height = int(frame.shape[0])
        box = _select_roi(
            f"StairKid {kind} platform calibration",
            frame,
            f"Select one complete {kind} platform and no surrounding objects.",
        )
        if kind == "normal":
            relative = Path(config.vision.normal_platform_template_path)
        elif kind == "spikes":
            relative = Path(config.vision.spikes_platform_template_path)
        elif kind == "spring":
            relative = Path(config.vision.green_platform_template_path)
        elif kind == "conveyor-1":
            relative = Path(config.vision.metal_platform_template_path)
        elif kind == "conveyor-2":
            relative = Path("captures/templates/platform_conveyor_2.png")
            value = relative.as_posix()
            if value not in config.vision.metal_platform_template_paths:
                config.vision.metal_platform_template_paths.append(value)
        else:
            variant = kind.rsplit("-", 1)[1]
            relative = Path(f"captures/templates/platform_flipping_{variant}.png")
            value = relative.as_posix()
            if value not in config.vision.flipping_platform_template_paths:
                config.vision.flipping_platform_template_paths.append(value)

    target_path = relative if relative.is_absolute() else root / relative
    left, top, width, height = box
    target_path.parent.mkdir(parents=True, exist_ok=True)
    save_image(target_path, frame[top : top + height, left : left + width])
    config.save(config_path)
    print(f"CALIBRATION_KIND={kind}")
    print(f"CALIBRATION_TEMPLATE={target_path.resolve()}")
    print("REAL_ACTIONS_SENT=0")
    return target_path.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Passive NS-SHAFT template calibration")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--kind", choices=KINDS, required=True)
    args = parser.parse_args()
    try:
        calibrate_kind(args.project_root, args.kind)
    except Exception as exc:
        print(f"CALIBRATION_FAILED={type(exc).__name__}:{exc}")
        print("REAL_ACTIONS_SENT=0")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
