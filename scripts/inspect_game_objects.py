from __future__ import annotations

import argparse
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

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
from stair_agent.game_events import describe_event_zh, GameplayEventDetector
from stair_agent.hud_detection import HealthTracker, HudDetector
from stair_agent.object_detection import ObjectDetector, PlatformKind
from stair_agent.object_tracking import (
    PlatformStabilizer,
    PlatformTracker,
    PlatformTrackingState,
    PlayerTracker,
)
from stair_agent.observation import ObservationBuilder, ObservationJsonlWriter
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
    parser.add_argument(
        "--record-jsonl",
        nargs="?",
        const=Path("__auto__"),
        type=Path,
        help=(
            "選擇性記錄每幀結構化觀測；省略路徑時在 logs/ "
            "建立帶時間戳的新檔案。"
        ),
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        help="選擇性的最長執行秒數；省略時持續到按 Esc。",
    )
    return parser.parse_args()


def platform_counts(objects) -> str:
    counts = Counter(item.kind.value for item in objects.platforms)
    return ",".join(
        f"{kind}={count}" for kind, count in sorted(counts.items())
    ) or "none"


def platform_counts_short(objects) -> str:
    counts = Counter(item.kind.value for item in objects.platforms)
    aliases = {
        "normal": "N",
        "spikes": "X",
        "spring": "S",
        "conveyor": "C",
        "flipping": "F",
    }
    return " ".join(
        f"{aliases.get(kind, kind[:1].upper())}:{count}"
        for kind, count in sorted(counts.items())
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
    record_path: Path | None = None,
    max_seconds: float | None = None,
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
    platform_tracker = PlatformTracker()
    platform_stabilizer = PlatformStabilizer(
        persistent_kinds={
            PlatformKind.CONVEYOR,
            PlatformKind.FLIPPING,
            PlatformKind.SPRING,
        },
        persistence_frames=2,
    )
    health_tracker = HealthTracker()
    gameplay_event_detector = GameplayEventDetector(
        landing_contact_gap=config.events.landing_contact_gap,
        spring_contact_gap=config.events.spring_contact_gap,
        correlation_frames=config.events.correlation_frames,
    )
    observation_builder = ObservationBuilder()
    writer = None
    if record_path is not None:
        if record_path == Path("__auto__"):
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            resolved = (
                PROJECT_ROOT
                / "logs"
                / f"observations_{stamp}.jsonl"
            )
        else:
            resolved = (
                record_path
                if record_path.is_absolute()
                else PROJECT_ROOT / record_path
            )
        writer = ObservationJsonlWriter(resolved)
        print(f"結構化觀測將寫入：{resolved}")
    recent_events = ""
    recent_event_until = 0.0
    deadline = (
        time.monotonic() + max_seconds
        if max_seconds is not None
        else None
    )
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        try:
            while True:
                started = time.perf_counter()
                frame = capture.capture()
                phase, state_score = state_detector.detect_with_score(frame)
                if phase is GamePhase.PLAYING:
                    now = time.monotonic()
                    raw_objects = object_detector.detect(frame)
                    platform_state = platform_tracker.update(raw_objects, now)
                    objects = platform_stabilizer.update(
                        platform_state.objects
                    )
                    platform_state = PlatformTrackingState(
                        objects,
                        platform_state.scroll_velocity_y,
                        platform_state.matched_platforms,
                    )
                    preview = object_detector.annotate(frame, objects)
                    tracking = player_tracker.update(objects, now)
                    health = hud_detector.detect_health(frame)
                    health_update = health_tracker.update(health.segments)
                    events = gameplay_event_detector.update(
                        tracking,
                        health_update,
                    )
                    if events:
                        recent_events = ",".join(
                            (
                                item.event.value
                                + (
                                    f":{item.source_platform.kind.value}"
                                    if item.source_platform is not None
                                    else ""
                                )
                            )
                            for item in events
                        )
                        recent_event_until = now + 1.5
                        print(
                            "事件："
                            + "、".join(
                                describe_event_zh(item) for item in events
                            )
                        )
                    if time.monotonic() >= recent_event_until:
                        recent_events = ""
                    observation = observation_builder.build(
                        timestamp=now,
                        phase=phase,
                        player_state=tracking,
                        platform_state=platform_state,
                        health=health_update,
                        events=events,
                    )
                    if writer is not None:
                        writer.write(observation)
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
                            f"#{tracking.nearest_platform_below.track_id}/"
                            f"{tracking.nearest_platform_below.kind.value}"
                            f"/gap={tracking.platform_vertical_gap}"
                        )
                    )
                    delta = (
                        ""
                        if health_update.delta is None
                        else f"{health_update.delta:+d}"
                    )
                    message = [
                        (
                            f"PLAY life={health.segments}{delta} "
                            f"event={recent_events or 'none'}"
                        ),
                        (
                            f"P=({player_text}) {tracking.motion.value} "
                            f"vx={tracking.velocity_x:.0f} "
                            f"vy={tracking.velocity_y:.0f} "
                            f"scroll={platform_state.scroll_velocity_y:.0f}"
                        ),
                        (
                            f"near={nearest} "
                            f"platforms={platform_counts_short(objects)}"
                        ),
                    ]
                else:
                    player_tracker.reset()
                    platform_tracker.reset()
                    platform_stabilizer.reset()
                    health_tracker.reset()
                    gameplay_event_detector.reset()
                    recent_events = ""
                    recent_event_until = 0.0
                    preview = frame.copy()
                    message = [f"{phase.value} score={state_score:.3f}"]
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
                if deadline is not None and time.monotonic() >= deadline:
                    print("已達最長執行時間，正常結束。")
                    break
        finally:
            if writer is not None:
                writer.close()
            cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    if args.max_seconds is not None and args.max_seconds <= 0:
        raise RuntimeError("--max-seconds 必須大於 0。")
    config = load_config()
    object_detector = ObjectDetector.from_config(config.vision, PROJECT_ROOT)
    hud_detector = HudDetector(config.hud)
    if args.offline:
        run_offline(object_detector, hud_detector)
        return
    state_detector = GameStateDetector.from_config(config.detection, PROJECT_ROOT)
    print("此工具只擷取與標記畫面，不會送出任何按鍵。按 Esc 離開。")
    run_live(
        object_detector,
        state_detector,
        hud_detector,
        args.record_jsonl,
        args.max_seconds,
    )


if __name__ == "__main__":
    run_main(main)
