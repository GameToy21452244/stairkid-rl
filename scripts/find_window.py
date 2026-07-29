from _common import WindowManager, find_target, load_config, run_main


def main() -> None:
    config = load_config()
    manager = WindowManager()
    windows = manager.list_windows()
    if not windows:
        print("目前沒有可列出的可見視窗。")
    else:
        print("目前可見視窗：")
        for item in windows:
            rect = item.rect
            client = item.client_rect
            print(
                f"  hwnd={item.hwnd:<10} 標題={item.title!r} "
                f"視窗=({rect.left},{rect.top},{rect.width}x{rect.height}) "
                f"client=({client.left},{client.top},{client.width}x{client.height})"
            )
    target = find_target(config, manager)
    print(f"\n最可能的目標視窗：{target.title!r}（hwnd={target.hwnd}）")


if __name__ == "__main__":
    run_main(main)
