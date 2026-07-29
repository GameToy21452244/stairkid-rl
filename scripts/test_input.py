import time

from _common import WindowError, WindowManager, find_target, load_config, run_main
from stair_agent.input_controller import InputController, InputError, SafetyMonitor


def countdown(seconds: int = 3) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"{remaining}...")
        time.sleep(1)


def main() -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    print(f"目標視窗：{target.title!r}（hwnd={target.hwnd}）")
    print(
        f"將測試左鍵 {config.controls.left_key!r} 與右鍵 "
        f"{config.controls.right_key!r}，各約 300 ms。"
    )
    print(f"任何時候按 {config.safety.emergency_stop_key.upper()} 可緊急停止。")
    answer = input("確認遊戲已在可安全測試的畫面？輸入 YES 繼續：").strip()
    if answer != "YES":
        print("未確認，已取消，沒有送出按鍵。")
        return
    try:
        manager.focus(target.hwnd)
        print("已自動切換至遊戲視窗。")
    except WindowError:
        print("Windows 拒絕自動切換前景，改用人工切換。")
        print("倒數開始後，請立即用滑鼠點一下 NS-SHAFT 遊戲視窗。")
    print("3 秒後會再次確認遊戲是否位於前景：")
    countdown()
    backend_name = config.controls.input_backend
    with InputController(
        config.controls, config.safety, manager, target.hwnd
    ) as controller:
        with SafetyMonitor(
            controller, config.safety.emergency_stop_key
        ):
            def operation() -> None:
                if not manager.is_foreground(target.hwnd):
                    raise InputError(
                        "倒數結束時遊戲仍不是前景視窗；沒有送出任何按鍵。"
                    )
                print("測試 LEFT...")
                controller.tap(config.controls.left_key, 300)
                controller.release_all()
                if controller.emergency_stopped:
                    raise InputError("已由 F8 中止。")
                time.sleep(1)
                print("測試 RIGHT...")
                controller.tap(config.controls.right_key, 300)
                controller.release_all()

            controller.run_safely(operation)
    print(f"測試完成（後端：{backend_name}），所有方向鍵已釋放。")


if __name__ == "__main__":
    run_main(main)
