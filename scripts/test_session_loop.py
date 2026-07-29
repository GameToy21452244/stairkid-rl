from __future__ import annotations

import argparse
import time
import winsound

from _common import (
    PROJECT_ROOT,
    WindowManager,
    find_target,
    load_config,
    run_main,
)

from stair_agent.dialog_handler import DialogActionHandler, DialogActionOutcome
from stair_agent.game_state import GamePhase, GameStateDetector
from stair_agent.input_controller import InputController, InputError, SafetyMonitor
from stair_agent.screen_capture import ScreenCapture
from stair_agent.session_controller import (
    SessionEvent,
    SessionState,
    SessionStateMachine,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "安全監看一個 NS-SHAFT 回合：必要時單次 Enter 開局，"
            "偵測死亡後停止，不控制左右鍵。"
        )
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=60.0,
        help="單回合最長監看秒數（預設：60）。",
    )
    parser.add_argument(
        "--consecutive-frames",
        type=int,
        default=3,
        help="狀態成立需要的連續幀數（預設：3）。",
    )
    return parser.parse_args()


def countdown(seconds: int = 3) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"{remaining}...", flush=True)
        try:
            winsound.Beep(880, 120)
        except RuntimeError:
            pass
        time.sleep(1)


def print_transition(machine: SessionStateMachine, transition) -> None:
    if transition.event is not SessionEvent.NONE:
        print(
            f"session: {transition.previous.value} → {transition.current.value} "
            f"event={transition.event.value} "
            f"rounds={machine.round_count} completed={machine.completed_rounds}"
        )


def main() -> None:
    args = parse_args()
    if args.max_seconds <= 0:
        raise RuntimeError("--max-seconds 必須大於 0。")
    if args.consecutive_frames <= 0:
        raise RuntimeError("--consecutive-frames 必須大於 0。")

    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    detector = GameStateDetector.from_config(config.detection, PROJECT_ROOT)
    print(f"目標：{target.title!r}，class={target.class_name!r}")
    print("本工具不控制左右鍵，死亡後不自動重開。")
    print(
        f"若起始為 DIALOG，最多送一次 {config.controls.restart_key!r}；"
        f"按 {config.safety.emergency_stop_key.upper()} 可停止。"
    )
    answer = input("確認執行單回合安全監看？輸入大寫 YES：").strip()
    if answer != "YES":
        print("未確認，已取消，沒有送出按鍵。")
        return
    print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
    countdown()
    if not manager.is_foreground(target.hwnd):
        raise InputError("倒數結束時遊戲不是前景視窗；沒有送出任何按鍵。")

    frame_delay = 1 / config.capture.target_fps
    max_frames = max(args.consecutive_frames * 5, args.consecutive_frames)
    machine = SessionStateMachine()
    with ScreenCapture(config.capture, manager, target.hwnd) as capture:
        with InputController(
            config.controls,
            config.safety,
            manager,
            target.hwnd,
        ) as controller:
            handler = DialogActionHandler(
                detector,
                controller,
                config.controls.restart_key,
                capture.capture,
                key_duration_ms=config.controls.restart_duration_ms,
                required_consecutive=args.consecutive_frames,
                max_observation_frames=max_frames,
                observation_delay_seconds=frame_delay,
            )
            with SafetyMonitor(controller, config.safety.emergency_stop_key):
                initial = handler.observe_stable()
                transition = machine.update(initial.phase)
                print_transition(machine, transition)
                print(
                    f"初始狀態：{initial.phase.value} "
                    f"(score={initial.score:.3f})"
                )

                if initial.phase is GamePhase.DIALOG:
                    machine.mark_starting()
                    result = handler.execute_once()
                    print(
                        "已送出一次開局鍵："
                        f"backend={config.controls.input_backend}，"
                        f"key={config.controls.restart_key!r}，"
                        f"duration={config.controls.restart_duration_ms} ms"
                    )
                    transition = machine.update(result.after.phase)
                    print_transition(machine, transition)
                    if result.outcome is not DialogActionOutcome.PLAYING:
                        print(
                            f"按鍵後結果={result.outcome.value}；"
                            "未進入 PLAYING，已停止且不再按第二次。"
                        )
                        return
                elif initial.phase is not GamePhase.PLAYING:
                    print("初始狀態不是 DIALOG 或 PLAYING，已停止。")
                    return

                print(
                    f"回合監看開始，最長 {args.max_seconds:.1f} 秒；"
                    "不會送出左右鍵。"
                )
                started = time.monotonic()
                while time.monotonic() - started < args.max_seconds:
                    if controller.emergency_stopped:
                        transition = machine.emergency_stop()
                        print_transition(machine, transition)
                        raise InputError("已由 F8 緊急停止。")
                    if not manager.is_foreground(target.hwnd):
                        controller.release_all()
                        raise InputError("遊戲失去前景，已停止監看並釋放按鍵。")
                    observation = handler.observe_stable()
                    transition = machine.update(observation.phase)
                    print_transition(machine, transition)
                    if transition.current is SessionState.ROUND_ENDED:
                        elapsed = time.monotonic() - started
                        print(
                            f"已偵測回合結束：elapsed={elapsed:.2f}s，"
                            f"phase={observation.phase.value}，"
                            f"score={observation.score:.3f}"
                        )
                        print("依安全規則停止，不自動重開下一回合。")
                        return
                    if transition.current is SessionState.UNKNOWN:
                        print("狀態無法穩定辨識，已停止。")
                        return
                print("已達監看時間上限，安全停止。")
    print("所有按鍵已釋放。")


if __name__ == "__main__":
    run_main(main)
