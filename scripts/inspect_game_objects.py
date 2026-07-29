from __future__ import annotations

import argparse
import time
from collections import Counter

from _common import (
    PROJECT_ROOT,
    WindowError,
    WindowManager,
    find_target,
    load_config,
    run_main,
)

import cv2

from stair_agent.diagnostics import (
    annotate_frame,
    load_image,
    prepare_preview_window,
)
from stair_agent.game_state import GamePhase, GameStateDetector
from stair_agent.game_events import GameEvent, SpringBounceDetector
from stair_agent.hud_detection import HealthTracker, HudDetector
from stair_agent.object_detection import ObjectDetector, PlatformKind
from stair_agent.object_tracking import PlatformStabilizer, PlayerTracker
from stair_agent.screen_capture import ScreenCapture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="離線或即時檢查角色、平台、移動與血量辨識；不控制遊戲。"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="只分析 captures/labeled 的 playing 圖片。",
    )
    return parser.parse_args()


def platform_counts(objects) -> str:
    counts = Counter(item.kind.value for item in objects.platforms)
    return ",".join(
        f"{kind}={count}" for kind, count in sorted(counts.items())
    ) or "none"


def run_offline(
    detector: ObjectDetector,
    hud_detector: HudDetector,
) -> None:
    paths = sorted(
        (PROJECT_ROOT / "captures" / "labeled").glob("*_playing.png")
    )
    if not paths:
        raise RuntimeError("captures/labeled 內沒有 playing PNG。")
    player_hits = 0
    for path in paths:
        frame = load_image(path)
        objects = detector.detect(frame)
        health = hud_detector.detect_health(frame)
        player_hits += int(objects.player is not None)
        player_text = (
            "none"
            if objects.player is None
            else (
                f"({objects.player.box.left},{objects.player.box.top},"
                f"{objects.player.box.width}x{objects.player.box.height})"
            )
        )
        print(
            f"player={player_text:<20} "
            f"platforms=[{platform_counts(objects)}] "
            f"life={health.segments} {path.name}"
        )
    print(f"\n角色命中：{player_hits}/{len(paths)}")


def run_live(
    object_detector: ObjectDetector,
    state_detector: GameStateDetector,
    hud_detector: HudDetector,
) -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    window_name = "NS-SHAFT 角色與平台辨識（不控制遊戲）"
    prepare_preview_window(window_name, target)
    try:
        manager.focus(target.hwnd)
    except WindowError:
        print("Windows 拒絕自動聚焦；請手動顯示遊戲且避免其他視窗遮住它。")
    delay_ms = max(1, round(1000 / config.capture.target_fps))
    player_tracker = PlayerTracker()
    platform_stabilizer = PlatformStabilizer(
        persistent_kinds={
            PlatformKind.CONVEYOR,
            PlatformKind.FLIPPING,
            PlatformKind.SPRING,
        },
        persistence_frames=2,
    )
    health_tracker = HealthTracker()
    spring_bounce_detector = SpringBounceDetector()
    recent_event = ""
    recent_event_until = 0.0
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        try:
            while True:
                started = time.perf_counter()
                frame = capture.capture()
                phase, state_score = state_detector.detect_with_score(frame)
                if phase is GamePhase.PLAYING:
                    objects = object_detector.detect(frame)
                    objects = platform_stabilizer.update(objects)
                    preview = object_detector.annotate(frame, objects)
                    tracking = player_tracker.update(objects, time.monotonic())
                    event = spring_bounce_detector.update(tracking)
                    if event.event is GameEvent.SPRING_BOUNCE:
                        recent_event = event.event.value
                        recent_event_until = time.monotonic() + 1.0
                        print("事件：角色踩到彈簧平台後向上反彈。")
                    if time.monotonic() >= recent_event_until:
                        recent_event = ""
                    health = hud_detector.detect_health(frame)
                    health_update = health_tracker.update(health.segments)
                    player_text = (
                        "none"
                        if objects.player is None
                        else (
                            f"{objects.player.box.center[0]:.0f},"
                            f"{objects.player.box.center[1]:.0f}"
                        )
                    )
                    nearest = (
                        "none"
                        if tracking.nearest_platform_below is None
                        else (
                            f"{tracking.nearest_platform_below.kind.value}"
                            f"/gap={tracking.platform_vertical_gap}"
                        )
                    )
                    delta = (
                        ""
                        if health_update.delta is None
                        else f"{health_update.delta:+d}"
                    )
                    message = (
                        f"PLAYING player={player_text} "
                        f"motion={tracking.motion.value} "
                        f"near={nearest} life={health.segments}{delta} "
                        f"event={recent_event or 'none'} "
                        f"[{platform_counts(objects)}]"
                    )
                else:
                    player_tracker.reset()
                    platform_stabilizer.reset()
                    health_tracker.reset()
                    spring_bounce_detector.reset()
                    recent_event = ""
                    recent_event_until = 0.0
                    preview = frame.copy()
                    message = f"{phase.value} score={state_score:.3f}"
                preview = annotate_frame(
                    preview,
                    capture.fps if config.diagnostics.show_fps else None,
                    config.diagnostics.draw_capture_border,
                    message,
                )
                cv2.imshow(window_name, preview)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                if cv2.waitKey(max(1, delay_ms - elapsed_ms)) & 0xFF == 27:
                    break
        finally:
            cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    config = load_config()
    object_detector = ObjectDetector.from_config(config.vision, PROJECT_ROOT)
    hud_detector = HudDetector(config.hud)
    if args.offline:
        run_offline(object_detector, hud_detector)
        return
    state_detector = GameStateDetector.from_config(config.detection, PROJECT_ROOT)
    print("此工具只擷取與標記畫面，不會送出任何按鍵。按 Esc 離開。")
    run_live(object_detector, state_detector, hud_detector)


if __name__ == "__main__":
    run_main(main)
