from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.live_env import create_live_environment
from stair_agent.rl_evaluation import (
    evaluate_policy,
    resolve_evaluation_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="以硬性步數、回合與時間上限評估本機 PPO 模型。"
    )
    parser.add_argument("--model")
    parser.add_argument("--max-steps", type=int, default=128)
    parser.add_argument("--max-episodes", type=int, default=3)
    parser.add_argument("--max-seconds", type=float, default=45.0)
    return parser.parse_args()


def bounded(value, *, minimum, maximum, name):
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} 必須介於 {minimum} 與 {maximum}。")
    return value


def main() -> None:
    args = parse_args()
    max_steps = bounded(
        args.max_steps,
        minimum=1,
        maximum=10_000,
        name="--max-steps",
    )
    max_episodes = bounded(
        args.max_episodes,
        minimum=1,
        maximum=20,
        name="--max-episodes",
    )
    max_seconds = bounded(
        args.max_seconds,
        minimum=5.0,
        maximum=600.0,
        name="--max-seconds",
    )
    model_path = resolve_evaluation_model(PROJECT_ROOT, args.model)
    config = load_config()
    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    try:
        # pywin32 必須先於 torch 載入，避免 Windows DLL 搜尋順序衝突。
        from stable_baselines3 import PPO

        model = PPO.load(model_path, device="cpu")
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print(f"評估模型：{model_path}")
        print(
            f"硬上限：steps={max_steps}，episodes={max_episodes}，"
            f"seconds={max_seconds:.1f}。"
        )
        print(
            "本工具使用 deterministic 動作，不更新模型。每次 reset "
            "最多送一次 Enter；F8、失焦或額外視窗會停止並釋放按鍵。"
        )
        if input("確認開始受限模型評估？輸入大寫 EVAL：").strip() != "EVAL":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        result = evaluate_policy(
            env,
            model,
            max_steps=max_steps,
            max_episodes=max_episodes,
            max_seconds=max_seconds,
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        summary_path = model_path.parent / f"evaluation_{stamp}.json"
        summary_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"受限評估結束：reason={result.stop_reason}，"
            f"steps={result.steps}，"
            f"episodes={result.completed_episodes}，"
            f"reward={result.total_reward:.2f}，"
            f"summary={summary_path}"
        )
    finally:
        env.close()


if __name__ == "__main__":
    run_main(main)
