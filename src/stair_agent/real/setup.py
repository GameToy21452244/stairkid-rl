"""First-run and live-profile validation without Real input side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil

from stair_agent.config import AppConfig


PLACEHOLDER_MARKERS = ("請使用者填入", "replace-me", "example title")


@dataclass(frozen=True)
class RealSetupReport:
    config_path: Path
    config_created: bool
    missing_templates: tuple[Path, ...]
    problems: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_templates and not self.problems


def initialize_local_config(project_root: Path) -> tuple[Path, bool]:
    root = Path(project_root).resolve()
    destination = root / "config.yaml"
    if destination.exists():
        return destination, False
    source = root / "config.example.yaml"
    if not source.is_file():
        raise RuntimeError(f"REAL_CONFIG_TEMPLATE_REQUIRED:{source}")
    shutil.copyfile(source, destination)
    return destination, True


def _resolve_local(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def inspect_real_setup(project_root: Path, *, initialize: bool = False) -> RealSetupReport:
    root = Path(project_root).resolve()
    if initialize:
        config_path, created = initialize_local_config(root)
    else:
        config_path, created = root / "config.yaml", False
    if not config_path.is_file():
        return RealSetupReport(config_path, created, (), ("REAL_CONFIG_REQUIRED",))

    config = AppConfig.load(config_path)
    problems: list[str] = []
    title = config.game.window_title_contains.strip()
    if not title or any(marker in title.casefold() for marker in PLACEHOLDER_MARKERS):
        problems.append("REAL_WINDOW_TITLE_NOT_CONFIGURED")
    if config.game.window_class_name is None:
        problems.append("REAL_WINDOW_CLASS_NOT_CONFIGURED")

    required_values = [
        config.detection.dialog_template_path,
        config.vision.normal_platform_template_path,
        config.vision.spikes_platform_template_path,
        config.vision.green_platform_template_path,
        config.vision.metal_platform_template_path,
        *config.vision.metal_platform_template_paths,
        *config.vision.flipping_platform_template_paths,
    ]
    missing = tuple(
        path
        for path in dict.fromkeys(_resolve_local(root, value) for value in required_values)
        if not path.is_file()
    )
    return RealSetupReport(config_path, created, missing, tuple(problems))


def print_report(report: RealSetupReport) -> None:
    print(f"REAL_CONFIG={report.config_path}")
    print(f"REAL_CONFIG_CREATED={'YES' if report.config_created else 'NO'}")
    for problem in report.problems:
        print(f"REAL_SETUP_PROBLEM={problem}")
    for path in report.missing_templates:
        print(f"MISSING_REAL_TEMPLATE={path}")
    print(f"REAL_RUNTIME_READY={'YES' if report.ready else 'NO'}")
    if not report.ready:
        print("NEXT_STEP=Run CALIBRATE_REAL_GAME.cmd before START_REAL_MODEL_TEST.cmd")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare/check the local Real profile.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = inspect_real_setup(args.project_root, initialize=args.initialize)
    print_report(report)
    return 0 if (report.ready or not args.check) else 4


if __name__ == "__main__":
    raise SystemExit(main())
