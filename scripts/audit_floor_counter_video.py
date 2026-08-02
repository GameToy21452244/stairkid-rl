from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.hud_detection import FloorCounterTracker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="從既有 MP4 重播 HUD floor counter，不載入真實輸入後端。"
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--expected-max", type=int, nargs="*")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "p36_floor_counter_video_audit.json",
    )
    return parser.parse_args()


def audit_video(path: Path, tracker: FloorCounterTracker) -> dict:
    tracker.reset()
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"無法開啟 MP4：{path}")
    frame_index = 0
    initial = None
    maximum = None
    unavailable_frames = 0
    unstable_frames = 0
    changes: list[dict[str, int]] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            update = tracker.update(frame)
            if update.value is None:
                unavailable_frames += 1
            else:
                value = int(update.value)
                initial = value if initial is None else initial
                maximum = value if maximum is None else max(maximum, value)
            if not update.stable:
                unstable_frames += 1
            if update.delta is not None and update.delta > 0:
                changes.append(
                    {
                        "frame": frame_index,
                        "value": int(update.value),
                    }
                )
            frame_index += 1
    finally:
        capture.release()
    if frame_index == 0:
        raise RuntimeError(f"MP4 沒有可讀 frame：{path}")
    return {
        "video": str(path),
        "frames": frame_index,
        "initial_floor": initial,
        "max_floor": maximum,
        "changes": changes,
        "unavailable_frames": unavailable_frames,
        "unstable_frames": unstable_frames,
    }


def main() -> None:
    args = parse_args()
    videos = sorted(args.run_dir.glob("episode_*.mp4"))
    if not videos:
        raise RuntimeError(f"找不到 episode MP4：{args.run_dir}")
    config = load_config()
    tracker = FloorCounterTracker(config.hud)
    episodes = [audit_video(path, tracker) for path in videos]
    observed = [item["max_floor"] for item in episodes]
    expected = args.expected_max
    expected_match = expected is None or observed == expected
    checks = {
        "all_videos_read": len(episodes) == len(videos),
        "counter_available_every_frame": all(
            item["unavailable_frames"] == 0 for item in episodes
        ),
        "initial_floor_one": all(
            item["initial_floor"] == config.hud.floor_counter_initial_value
            for item in episodes
        ),
        "expected_manual_max_match": expected_match,
    }
    payload = {
        "experiment": "p36-floor-counter-video-audit",
        "source_run": str(args.run_dir),
        "method": "calibrated HUD binary-change tracker with stable-frame debounce",
        "privileged_state_used": False,
        "episodes": episodes,
        "observed_max_floors": observed,
        "expected_manual_max_floors": expected,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f"拒絕覆寫既有 audit：{args.output}")
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_main(main)
