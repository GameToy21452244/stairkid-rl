from __future__ import annotations

import argparse
import time

from _common import PROJECT_ROOT, load_config, run_main

from gymnasium.utils.env_checker import check_env

from stair_agent.game_state import GamePhase
from stair_agent.gym_env import StairAgentEnv
from stair_agent.live_env import create_live_environment
from stair_agent.observation import GameObservation


def empty_playing_observation() -> GameObservation:
    return GameObservation(
        timestamp=time.monotonic(),
        phase=GamePhase.PLAYING.value,
        player=None,
        health={"segments": 12, "delta": 0, "event": "unchanged"},
        nearest_platform=None,
        platforms=[],
        platform_scroll_velocity_y=0.0,
        events=[],
    )


class MockAdapter:
    """只供本腳本的離線介面檢查；不載入任何輸入後端。"""

    def reset(self) -> GameObservation:
        return empty_playing_observation()

    def step(self, _action) -> GameObservation:
        return empty_playing_observation()

    def release_all(self) -> None:
        return None

    def close(self) -> None:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="檢查 Gymnasium 介面；預設為完全離線 mock。"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="互動式實機測試 5 個預先列明的動作。",
    )
    return parser.parse_args()


def check_mock() -> None:
    config = load_config()
    env = StairAgentEnv(MockAdapter(), config.environment)
    try:
        check_env(env, skip_render_check=True)
    finally:
        env.close()
    print("Gymnasium mock 檢查通過；未尋找遊戲，也未操作鍵盤或滑鼠。")


def check_live() -> None:
    config = load_config()
    env, target = create_live_environment(config, PROJECT_ROOT)
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
        print("本工具不會按 Enter、重開遊戲或執行隨機動作。")
        print("請先手動讓角色進入遊玩中（PLAYING）。將依序測試：")
        for index, description in actions:
            print(f"  {index} = {description}")
        print("任一時刻可按 F8 緊急停止；失焦或例外也會釋放方向鍵。")
        if input("確認執行？輸入大寫 YES：").strip() != "YES":
            print("未確認，已安全取消。")
            return
        print("看到 3... 後立即點選遊戲，之後不要切換視窗。")
        for value in (3, 2, 1):
            print(f"{value}...")
            time.sleep(1)

        observation, info = env.reset()
        print(f"reset 通過：phase={info['phase']}，features={observation.shape}")
        for action, description in actions:
            _obs, reward, terminated, truncated, info = env.step(action)
            print(
                f"action={action} ({description}) reward={reward:.2f} "
                f"phase={info['phase']} events={info['events']}"
            )
            if terminated or truncated:
                print(
                    "環境已終止或截斷；不會繼續送出後續動作。"
                )
                break
        print("Gymnasium 實機安全檢查完成。")
    finally:
        env.close()


def main() -> None:
    if parse_args().live:
        check_live()
    else:
        check_mock()


if __name__ == "__main__":
    run_main(main)
