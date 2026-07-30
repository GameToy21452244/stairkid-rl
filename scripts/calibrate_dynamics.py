from __future__ import annotations

import argparse
import time
from datetime import datetime

from _common import PROJECT_ROOT, load_config, run_main
from stair_agent.baseline_policy import SafePlatformPolicy
from stair_agent.data.validator import DatasetValidator
from stair_agent.data.writer import (
    TransitionJsonlWriter,
    extract_reward_terms,
)
from stair_agent.input_controller import Action
from stair_agent.live_env import LiveGameAdapter, create_live_environment


def action_sequence(mode: str) -> list[Action]:
    if mode == "passive":
        return [Action.RELEASE_ALL] * 56
    if mode == "landing-focused":
        return [Action.RELEASE_ALL] * 120
    if mode == "momentum-release":
        actions = [Action.RELEASE_ALL] * 4
        # The game removes most horizontal momentum on the first release
        # frame.  Short alternating pulses therefore produce substantially
        # more identifiable non-zero release samples than long release runs,
        # without increasing the existing 52-step safety bound.
        for _ in range(6):
            actions += [Action.LEFT] * 2 + [Action.RELEASE_ALL] * 2
            actions += [Action.RIGHT] * 2 + [Action.RELEASE_ALL] * 2
        return actions
    actions = [Action.RELEASE_ALL] * 4
    directions = (
        (Action.RIGHT, Action.LEFT)
        if mode == "right-first"
        else (Action.LEFT, Action.RIGHT)
    )
    for duration in (1, 2, 3, 4):
        actions += [directions[0]] * duration
        actions += [Action.RELEASE_ALL] * 4
        actions += [directions[1]] * duration
        actions += [Action.RELEASE_ALL] * 4
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="單回合、固定序列的 NS-SHAFT 物理校正。"
    )
    parser.add_argument(
        "--mode",
        choices=(
            "left-first",
            "right-first",
            "passive",
            "momentum-release",
            "landing-focused",
        ),
        default="left-first",
    )
    args = parser.parse_args()
    config = load_config()
    actions = action_sequence(args.mode)
    max_seconds = 20.0
    env, target = create_live_environment(
        config, PROJECT_ROOT, allow_single_enter_reset=True
    )
    adapter = env.adapter
    if not isinstance(adapter, LiveGameAdapter):
        env.close()
        raise RuntimeError("實機 adapter 類型不符。")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = (
        PROJECT_ROOT
        / "logs"
        / f"calibration_v1_{args.mode}_{stamp}.jsonl"
    )
    writer = None
    try:
        print(
            f"目標：{target.title!r} client="
            f"{target.client_rect.width}x{target.client_rect.height}"
        )
        print(
            f"只執行 1 回合、最多 {len(actions)} 步／{max_seconds:.0f} 秒；"
            f"mode={args.mode}。"
        )
        print("F8、失焦、額外視窗、死亡、未知狀態或例外會立即停止並放開按鍵。")
        if input("確認有限物理校正？輸入大寫 CALIBRATE：").strip() != "CALIBRATE":
            print("未確認，已安全取消。")
            return
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)
        if not adapter.is_foreground():
            raise RuntimeError("倒數後遊戲不是前景視窗，拒絕送鍵。")
        observation, info = env.reset()
        if env.last_observation is None:
            raise RuntimeError("reset 後缺少原始觀測。")
        writer = TransitionJsonlWriter(path, policy_source="invalid")
        writer.begin(
            observation,
            observation_timestamp=env.last_observation.timestamp,
        )
        deadline = time.monotonic() + max_seconds
        written = 0
        policy = SafePlatformPolicy(config.baseline)
        for index, action in enumerate(actions):
            if time.monotonic() >= deadline:
                print("已達時間上限。")
                break
            if adapter.emergency_stopped or not adapter.is_foreground():
                print("F8、失焦或阻擋視窗出現，停止。")
                break
            if args.mode == "landing-focused":
                action = policy.choose(env.last_observation).action
            next_features, reward, terminated, truncated, info = env.step(int(action))
            timing = adapter.last_action_timing
            if timing is None or not timing.action_applied:
                print("動作未實際送出（phase 已改變），停止且不寫入該步。")
                break
            raw = env.last_observation
            if raw is None:
                raise RuntimeError("step 後缺少原始觀測。")
            writer.write_step(
                action=int(action),
                reward=reward,
                reward_components=extract_reward_terms(
                    info["reward_components"]
                ),
                next_observation=next_features,
                terminated=terminated,
                truncated=(
                    truncated
                    or (
                        not terminated
                        and index == len(actions) - 1
                    )
                ),
                events=raw.events,
                timing=timing,
            )
            written += 1
            if terminated or truncated:
                print(f"回合結束：terminated={terminated} truncated={truncated}")
                break
        print(f"已寫入 {written} 筆 calibration transitions：{path}")
    finally:
        if writer is not None:
            writer.close()
        env.close()
    if path.exists():
        report = DatasetValidator().validate_file(path)
        print(
            f"validator：valid={report.valid} errors={report.error_count} "
            f"warnings={report.warning_count}"
        )
        if not report.valid:
            raise RuntimeError("校正資料未通過 validator，保持 invalid/quarantine。")


if __name__ == "__main__":
    run_main(main)
