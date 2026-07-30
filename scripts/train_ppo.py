from __future__ import annotations

import argparse
import time
from dataclasses import replace
from datetime import datetime

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.live_env import create_live_environment
from stair_agent.rl_evaluation import resolve_evaluation_model
from stair_agent.rl_training import (
    SafetyStopCallback,
    TrainingSafetyWrapper,
    create_ppo_model,
    load_ppo_model,
    resolve_model_directory,
    validate_training_budget,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="執行具有回合、時間與步數硬上限的本機 PPO 訓練。"
    )
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--max-episodes", type=int)
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument(
        "--resume-model",
        help=(
            "只允許載入專案 models/ 內的既有 .zip，"
            "並在新的執行目錄繼續訓練。"
        ),
    )
    parser.add_argument(
        "--focus-target",
        action="store_true",
        help="倒數後只嘗試一次將已驗證的遊戲視窗切到前景。",
    )
    return parser.parse_args()


def bounded(value, default, *, minimum, maximum, name):
    result = default if value is None else value
    if not minimum <= result <= maximum:
        raise RuntimeError(
            f"{name} 必須介於 {minimum} 與 {maximum}。"
        )
    return result


def main() -> None:
    args = parse_args()
    config = load_config()
    training = replace(
        config.training,
        total_timesteps=bounded(
            args.timesteps,
            config.training.total_timesteps,
            minimum=32,
            maximum=100_000,
            name="--timesteps",
        ),
        max_episodes=bounded(
            args.max_episodes,
            config.training.max_episodes,
            minimum=1,
            maximum=100,
            name="--max-episodes",
        ),
        max_training_seconds=bounded(
            args.max_seconds,
            config.training.max_training_seconds,
            minimum=5.0,
            maximum=3600.0,
            name="--max-seconds",
        ),
    )
    validate_training_budget(training)
    model_root = resolve_model_directory(
        PROJECT_ROOT,
        training.model_dir,
    )
    resume_path = (
        None
        if args.resume_model is None
        else resolve_evaluation_model(
            PROJECT_ROOT,
            args.resume_model,
        )
    )
    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    wrapped = TrainingSafetyWrapper(
        env,
        max_episodes=training.max_episodes,
    )
    # Windows 上 torch 先載入時可能改變 DLL 搜尋順序，導致後載入的
    # win32gui 失敗。create_live_environment 已先完成 pywin32 載入，
    # 因此 SB3 callback 也必須延遲到這裡才匯入。
    from stable_baselines3.common.callbacks import CheckpointCallback

    model = None
    run_dir = None
    try:
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print(
            "警告：PPO 初期會探索，可能快速左右切換、踩刺或摔落；"
            "這是訓練動作，不是規則基準。"
        )
        print(
            f"硬上限：timesteps={training.total_timesteps}，"
            f"episodes={training.max_episodes}，"
            f"seconds={training.max_training_seconds:.1f}。"
        )
        if resume_path is not None:
            print(f"續訓來源：{resume_path}")
        print(
            "每次回合 reset 最多送一次 Enter；最後核准回合死亡時"
            "會阻止自動重開。F8、失焦或額外視窗會停止並釋放按鍵。"
        )
        if input("確認開始受限 PPO 訓練？輸入大寫 TRAIN：").strip() != "TRAIN":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)
        if args.focus_target:
            env.adapter.controller.window_manager.focus(target.hwnd)
            time.sleep(0.2)
            if not env.adapter.is_foreground():
                raise RuntimeError(
                    "嘗試切換後遊戲仍不是前景視窗；已停止。"
                )
            print("遊戲前景切換與驗證通過。")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = model_root / stamp
        checkpoint_dir = run_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        model = (
            create_ppo_model(wrapped, training, verbose=1)
            if resume_path is None
            else load_ppo_model(
                wrapped,
                resume_path,
                training,
                verbose=1,
            )
        )
        safety_callback = SafetyStopCallback(
            max_seconds=training.max_training_seconds,
        )
        checkpoint_callback = CheckpointCallback(
            save_freq=training.checkpoint_freq_steps,
            save_path=str(checkpoint_dir),
            name_prefix="ppo_stair",
        )
        model.learn(
            total_timesteps=training.total_timesteps,
            callback=[safety_callback, checkpoint_callback],
            progress_bar=False,
            reset_num_timesteps=resume_path is None,
        )
        final_path = run_dir / "final_model"
        model.save(final_path)
        stop_reason = (
            safety_callback.stop_reason
            or "timesteps_limit"
        )
        print(
            f"受限訓練結束：reason={stop_reason}，"
            f"completed_episodes={wrapped.completed_episodes}，"
            f"model={final_path.with_suffix('.zip')}"
        )
        print(
            f"實際訓練動作：{wrapped.action_counts}，"
            f"最長連續同動作={wrapped.longest_same_action_streak}"
        )
        print(f"Reward 累計：{wrapped.reward_component_totals}")
    except KeyboardInterrupt:
        if model is not None and run_dir is not None:
            model.save(run_dir / "interrupted_model")
        raise
    finally:
        wrapped.close()


if __name__ == "__main__":
    run_main(main)
