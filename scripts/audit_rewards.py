from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from _common import PROJECT_ROOT, load_config, run_main

from stair_agent.game_state import GamePhase
from stair_agent.gym_env import FeatureEncoder, GymEnvironmentError
from stair_agent.live_env import LiveGameAdapter, create_live_environment
from stair_agent.observation import GameObservation
from stair_agent.trajectory import RewardAuditor, TrajectoryJsonlWriter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="稽核短回合的觀測、事件與 reward；不執行模型訓練。"
    )
    parser.add_argument(
        "--offline",
        type=Path,
        help="重播既有 observations 或 trajectory JSONL，不尋找遊戲。",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=30.0,
        help="實機人工遊玩稽核秒數，預設 30。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="輸出 JSONL；實機省略時自動寫到 logs/。",
    )
    return parser.parse_args()


def resolve_output(path: Path | None) -> Path:
    if path is not None:
        return path if path.is_absolute() else PROJECT_ROOT / path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return PROJECT_ROOT / "logs" / f"reward_audit_{stamp}.jsonl"


def make_offline_encoder(config) -> FeatureEncoder:
    width = (
        config.vision.reference_width
        or config.detection.reference_width
        or config.capture.resize_width
        or config.capture.width
        or 634
    )
    height = (
        config.vision.reference_height
        or config.detection.reference_height
        or config.capture.resize_height
        or config.capture.height
        or 431
    )
    return FeatureEncoder(
        reference_width=width,
        reference_height=height,
        velocity_scale=config.environment.velocity_scale,
        max_platforms_per_type=config.environment.max_platforms_per_type,
    )


def print_event(step: int, observation: GameObservation, reward: float) -> None:
    if observation.events or reward:
        names = [
            str(item.get("type", "unknown"))
            for item in observation.events
        ]
        health = observation.health.get("segments")
        print(
            f"step={step} reward={reward:+.2f} life={health} "
            f"events={names or []}"
        )


def print_summary(summary: dict) -> None:
    print(
        "稽核摘要："
        f"steps={summary['steps']}，"
        f"total_reward={summary['total_reward']:.2f}，"
        f"end_reason={summary['end_reason'] or '資料結束'}"
    )
    print(f"事件統計：{summary['event_counts'] or {}}")


def load_observation(line: str, line_number: int) -> GameObservation:
    try:
        payload = json.loads(line)
        data = payload.get("observation", payload)
        return GameObservation(**data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"JSONL 第 {line_number} 行格式無效：{exc}"
        ) from exc


def audit_offline(path: Path, output: Path | None) -> None:
    source = path if path.is_absolute() else PROJECT_ROOT / path
    if not source.is_file():
        raise RuntimeError(f"找不到離線觀測檔：{source}")
    config = load_config()
    encoder = make_offline_encoder(config)
    auditor = RewardAuditor(config.environment)
    writer = TrajectoryJsonlWriter(resolve_output(output)) if output else None
    try:
        with source.open(encoding="utf-8") as source_file:
            for step, line in enumerate(source_file, start=1):
                if not line.strip():
                    continue
                observation = load_observation(line, step)
                result = auditor.evaluate(observation)
                features = encoder.encode(observation)
                if writer is not None:
                    writer.write(
                        step=step,
                        action="replay",
                        observation=observation,
                        features=features,
                        result=result,
                        cumulative_reward=auditor.total_reward,
                    )
                print_event(step, observation, result.reward)
    finally:
        if writer is not None:
            writer.close(auditor.summary())
    print_summary(auditor.summary())


def audit_live(max_seconds: float, output: Path | None) -> None:
    if max_seconds <= 0:
        raise RuntimeError("--max-seconds 必須大於 0。")
    config = load_config()
    env, target = create_live_environment(config, PROJECT_ROOT)
    adapter = env.adapter
    if not isinstance(adapter, LiveGameAdapter):
        env.close()
        raise RuntimeError("實機環境 adapter 類型不符。")
    path = resolve_output(output)
    writer = None
    auditor = RewardAuditor(config.environment)
    try:
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print("本工具只旁觀與記錄；左右鍵完全由你親自操作。")
        print("不會按 Enter、不會自動重開，也不會執行隨機動作。")
        print(f"最長 {max_seconds:.1f} 秒；F8、失焦或死亡會停止並釋放按鍵。")
        if input("確認開始人工遊玩稽核？輸入大寫 YES：").strip() != "YES":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲並用左右鍵正常遊玩。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        initial = adapter.reset()
        if initial.phase != GamePhase.PLAYING.value:
            raise GymEnvironmentError(
                "開始稽核前必須手動進入 PLAYING；"
                f"目前為 {initial.phase!r}。"
            )
        writer = TrajectoryJsonlWriter(path)
        print(f"軌跡將寫入：{path}")
        deadline = time.monotonic() + max_seconds
        step = 0
        delay = 1.0 / config.capture.target_fps
        while True:
            started = time.monotonic()
            if adapter.emergency_stopped:
                auditor.finish("emergency_stop")
                print("已偵測 F8，停止稽核。")
                break
            if not adapter.is_foreground():
                auditor.finish("focus_lost")
                print("遊戲已失去前景，停止稽核。")
                break
            observation = adapter.observe()
            step += 1
            result = auditor.evaluate(observation)
            features = env.encoder.encode(observation)
            writer.write(
                step=step,
                action="manual",
                observation=observation,
                features=features,
                result=result,
                cumulative_reward=auditor.total_reward,
            )
            print_event(step, observation, result.reward)
            if result.terminated or result.truncated:
                print(f"回合結束：phase={observation.phase}")
                break
            if time.monotonic() >= deadline:
                auditor.finish("time_limit")
                print("已達時間上限，正常停止。")
                break
            remaining = delay - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        auditor.finish("ctrl_c")
        raise
    finally:
        if writer is not None:
            writer.close(auditor.summary())
        env.close()
    print_summary(auditor.summary())
    print(f"摘要檔：{path.with_suffix('.summary.json')}")


def main() -> None:
    args = parse_args()
    if args.offline is not None:
        audit_offline(args.offline, args.output)
    else:
        audit_live(args.max_seconds, args.output)


if __name__ == "__main__":
    run_main(main)
