from __future__ import annotations

import time

from _common import PROJECT_ROOT, load_config, run_main

import numpy as np

from stair_agent.live_env import create_live_environment


def expected_action_features(action: int) -> list[float]:
    values = [0.0, 0.0, 0.0]
    values[action] = 1.0
    return values


def main() -> None:
    config = load_config()
    if not config.environment.include_action_history:
        raise RuntimeError(
            "本工具需要 environment.include_action_history=true。"
        )
    env, target = create_live_environment(
        config,
        PROJECT_ROOT,
        allow_single_enter_reset=True,
    )
    actions = [
        (0, "全部放開"),
        (1, f"左鍵 {config.controls.action_duration_ms} ms"),
        (0, "全部放開"),
        (2, f"右鍵 {config.controls.action_duration_ms} ms"),
        (0, "全部放開"),
    ]
    try:
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        print(
            "本工具只驗證固定 5 個動作的時序觀測；"
            "不執行隨機策略或訓練模型。"
        )
        print(
            "若起始為主遊戲 DIALOG，reset 最多送一次 Enter；"
            "死亡後不會重開第二回合。"
        )
        for action, description in actions:
            print(f"  {action} = {description}")
        print("F8、失焦、額外視窗、例外或回合終止都會立即停止並釋放按鍵。")
        if input("確認執行時序觀測實機檢查？輸入大寫 YES：").strip() != "YES":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        features, info = env.reset()
        frame_width = (
            info["raw_feature_count"] + 3
        )
        chunks = features.reshape(info["history_frames"], frame_width)
        if not np.all(chunks[:, -3:] == 0.0):
            raise RuntimeError("reset 後動作歷史不是全零。")
        print(
            f"reset 通過：phase={info['phase']}，"
            f"raw={info['raw_feature_count']}，"
            f"history={info['history_frames']}，"
            f"stacked={features.shape}"
        )

        for action, description in actions:
            features, reward, terminated, truncated, info = env.step(action)
            chunks = features.reshape(info["history_frames"], frame_width)
            actual = chunks[-1, -3:].tolist()
            expected = expected_action_features(action)
            if actual != expected:
                raise RuntimeError(
                    f"動作歷史不符：expected={expected}, actual={actual}"
                )
            print(
                f"action={action} ({description}) "
                f"latest_action={actual} shape={features.shape} "
                f"reward={reward:+.2f} phase={info['phase']} "
                f"events={info['events']}"
            )
            if terminated or truncated:
                print("環境已終止或截斷；不會送出後續動作。")
                break
        print("時序觀測實機檢查完成。")
    finally:
        env.close()


if __name__ == "__main__":
    run_main(main)
