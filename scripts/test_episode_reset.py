from __future__ import annotations

import argparse
import time

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.game_state import GamePhase
from stair_agent.live_env import LiveGameAdapter, create_live_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="測試每回合最多一次 Enter 的受限重設；不控制左右鍵。"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=2,
        help="測試回合數，允許 1–3，預設 2。",
    )
    parser.add_argument(
        "--max-seconds-per-round",
        type=float,
        default=30.0,
        help="每回合最長監看秒數，預設 30。",
    )
    return parser.parse_args()


def wait_for_round_end(
    adapter: LiveGameAdapter,
    *,
    max_seconds: float,
    target_fps: int,
    required_consecutive: int,
) -> str:
    deadline = time.monotonic() + max_seconds
    dialog_frames = 0
    delay = 1.0 / target_fps
    while True:
        started = time.monotonic()
        if adapter.emergency_stopped:
            return "emergency_stop"
        if not adapter.is_foreground():
            return "focus_lost"
        observation = adapter.observe()
        if observation.phase == GamePhase.DIALOG.value:
            dialog_frames += 1
            if dialog_frames >= required_consecutive:
                return "dialog"
        elif observation.phase == GamePhase.PLAYING.value:
            dialog_frames = 0
        else:
            return observation.phase
        if time.monotonic() >= deadline:
            return "time_limit"
        remaining = delay - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(remaining)


def main() -> None:
    args = parse_args()
    if not 1 <= args.cycles <= 3:
        raise RuntimeError("--cycles 只允許 1–3。")
    if args.max_seconds_per_round <= 0:
        raise RuntimeError("--max-seconds-per-round 必須大於 0。")

    config = load_config()
    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    adapter = env.adapter
    if not isinstance(adapter, LiveGameAdapter):
        env.close()
        raise RuntimeError("實機環境 adapter 類型不符。")
    try:
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print(
            f"將測試最多 {args.cycles} 回合；"
            "每次 reset 最多只送一個 Enter。"
        )
        print("本工具不控制左右鍵，也不處理或聚焦外部姓名輸入視窗。")
        print(
            "Enter 後若未進入 PLAYING、遊戲失焦、狀態不明或 F8，"
            "會立即停止且不補按第二次。"
        )
        if input("確認執行受限重設測試？輸入大寫 YES：").strip() != "YES":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        for cycle in range(1, args.cycles + 1):
            if adapter.emergency_stopped:
                print("已偵測 F8，停止測試。")
                break
            if not adapter.is_foreground():
                print("遊戲不是前景視窗，停止測試。")
                break
            observation, info = env.reset()
            resetter = adapter.episode_resetter
            enter_sent = bool(
                resetter is not None and resetter.last_enter_sent
            )
            print(
                f"回合 {cycle}/{args.cycles} reset 通過："
                f"phase={info['phase']}，enter_sent={enter_sent}，"
                f"features={observation.shape}"
            )
            reason = wait_for_round_end(
                adapter,
                max_seconds=args.max_seconds_per_round,
                target_fps=config.capture.target_fps,
                required_consecutive=(
                    config.environment.reset_required_consecutive_frames
                ),
            )
            print(f"回合 {cycle} 監看結束：reason={reason}")
            if reason != "dialog":
                print("未取得穩定死亡對話框，不會開始下一回合。")
                break
            if cycle == args.cycles:
                print("已達預先核准回合數，不會再次按 Enter。")
        print("受限重設測試安全結束。")
    finally:
        env.close()


if __name__ == "__main__":
    run_main(main)
