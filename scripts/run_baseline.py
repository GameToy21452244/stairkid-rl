from __future__ import annotations

import argparse
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.live_env import LiveGameAdapter, create_live_environment
from stair_agent.trajectory import RewardAuditor, TrajectoryJsonlWriter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="執行單回合可解釋平台策略基準；不訓練模型、不使用隨機動作。"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        help="覆蓋 baseline.max_episode_steps；硬上限 1000。",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        help="覆蓋 baseline.max_episode_seconds；硬上限 120 秒。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    max_steps = args.max_steps or config.baseline.max_episode_steps
    max_seconds = args.max_seconds or config.baseline.max_episode_seconds
    if not 1 <= max_steps <= 1000:
        raise RuntimeError("--max-steps 必須介於 1–1000。")
    if not 0 < max_seconds <= 120:
        raise RuntimeError("--max-seconds 必須大於 0 且不超過 120。")

    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    adapter = env.adapter
    if not isinstance(adapter, LiveGameAdapter):
        env.close()
        raise RuntimeError("實機環境 adapter 類型不符。")
    policy = SafePlatformPolicy(config.baseline)
    auditor = RewardAuditor(config.environment)
    writer = None
    action_counts: Counter[str] = Counter()
    try:
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print("這是規則基準，不是強化學習，也不會更新或建立模型。")
        print(
            "策略會先選可達安全落點，再短按左／右；"
            "接近尖刺會離台，頂端危險時會偏好更深落點。"
        )
        print(
            f"只跑 1 回合，最多 {max_steps} 步或 {max_seconds:.1f} 秒；"
            "死亡後不會重開第二回合。"
        )
        print(
            "主視窗失焦、額外遊戲視窗、F8、未知狀態或例外都會停止。"
        )
        if input("確認執行單回合規則基準？輸入大寫 YES：").strip() != "YES":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        features, info = env.reset()
        policy.reset()
        if env.last_observation is None:
            raise RuntimeError("reset 後缺少原始觀測。")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = PROJECT_ROOT / "logs" / f"baseline_{stamp}.jsonl"
        writer = TrajectoryJsonlWriter(path)
        print(
            f"reset 通過：phase={info['phase']}，features={features.shape}"
        )
        print(f"軌跡將寫入：{path}")
        deadline = time.monotonic() + max_seconds
        last_action = None
        for step in range(1, max_steps + 1):
            if adapter.emergency_stopped:
                auditor.finish("emergency_stop")
                print("已偵測 F8，停止基準。")
                break
            if not adapter.is_foreground():
                auditor.finish("window_blocked_or_focus_lost")
                print("遊戲失焦或出現額外遊戲視窗，停止基準。")
                break

            decision_observation = env.last_observation
            decision = policy.choose(decision_observation)
            action_counts[decision.action.name] += 1
            features, reward, terminated, truncated, info = env.step(
                int(decision.action)
            )
            observation = env.last_observation
            if observation is None:
                raise RuntimeError("step 後缺少原始觀測。")
            audit = auditor.evaluate(observation)
            if abs(audit.reward - reward) > 1e-9:
                raise RuntimeError("Gym reward 與稽核器結果不一致。")
            writer.write(
                step=step,
                action=int(decision.action),
                observation=observation,
                features=features,
                result=audit,
                cumulative_reward=auditor.total_reward,
                policy_decision={
                    "reason": decision.reason,
                    "target_platform_id": decision.target_platform_id,
                    "target_platform_kind": decision.target_platform_kind,
                    "horizontal_delta": decision.horizontal_delta,
                },
                decision_observation=decision_observation,
            )
            if (
                decision.action is not last_action
                or info["events"]
                or reward
            ):
                print(
                    f"step={step} action={decision.action.name} "
                    f"target=#{decision.target_platform_id}/"
                    f"{decision.target_platform_kind} "
                    f"dx={decision.horizontal_delta} "
                    f"reward={reward:+.2f} events={info['events']}"
                )
            last_action = decision.action
            if terminated or truncated:
                print(
                    f"回合結束：phase={info['phase']} "
                    f"terminated={terminated} truncated={truncated}"
                )
                break
            if time.monotonic() >= deadline:
                auditor.finish("time_limit")
                print("已達時間上限，停止基準。")
                break
        else:
            auditor.finish("step_limit")
            print("已達步數上限，停止基準。")
    except KeyboardInterrupt:
        auditor.finish("ctrl_c")
        raise
    finally:
        if writer is not None:
            summary = auditor.summary()
            summary["action_counts"] = dict(sorted(action_counts.items()))
            writer.close(summary)
        env.close()

    summary = auditor.summary()
    print(
        f"基準摘要：steps={summary['steps']}，"
        f"reward={summary['total_reward']:.2f}，"
        f"end_reason={summary['end_reason']}"
    )
    print(f"動作統計：{dict(sorted(action_counts.items()))}")
    print("單回合基準安全結束；沒有開始下一回合。")


if __name__ == "__main__":
    run_main(main)
