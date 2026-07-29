from _common import PROJECT_ROOT, WindowManager, find_target, load_config, run_main
from stair_agent.calibration import CaptureCalibrator


def main() -> None:
    config = load_config()
    manager = WindowManager()
    target = find_target(config, manager)
    print(f"正在校正：{target.title!r}")
    print("H/L 左右移動，K/J 上下移動，A/D 調寬，W/X 調高。")
    CaptureCalibrator(
        config,
        manager,
        target.hwnd,
        PROJECT_ROOT / "config.yaml",
        PROJECT_ROOT / "captures" / "calibration",
    ).run()


if __name__ == "__main__":
    run_main(main)
