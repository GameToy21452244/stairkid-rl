from __future__ import annotations

import sys
from pathlib import Path

# Windows 傳統 CP950 主控台可能無法顯示部分視窗標題；不得因此中斷偵測。
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        reconfigure(errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stair_agent.config import AppConfig, ConfigError  # noqa: E402
from stair_agent.window_manager import WindowError, WindowInfo, WindowManager  # noqa: E402


def load_config() -> AppConfig:
    return AppConfig.load(PROJECT_ROOT / "config.yaml")


def find_target(
    config: AppConfig, manager: WindowManager, allow_launch: bool = True
) -> WindowInfo:
    try:
        target = manager.require_ready(
            config.game.window_title_contains,
            config.game.window_class_name,
        )
        print(
            f"遊戲視窗檢查通過：{target.title!r}，"
            f"client={target.client_rect.width}x{target.client_rect.height}"
        )
        return target
    except WindowError:
        if not allow_launch or not config.game.auto_launch:
            raise
    exe_path = config.validated_exe_path()
    print(f"auto_launch=true，正在啟動設定中的遊戲：{exe_path}")
    manager.launch_if_enabled(
        exe_path, enabled=True, wait_seconds=config.game.launch_wait_seconds
    )
    target = manager.require_ready(
        config.game.window_title_contains,
        config.game.window_class_name,
    )
    print(
        f"遊戲視窗檢查通過：{target.title!r}，"
        f"client={target.client_rect.width}x{target.client_rect.height}"
    )
    return target


def run_main(main) -> None:
    try:
        main()
    except (ConfigError, WindowError, RuntimeError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\n已收到 Ctrl+C，安全結束。")
