"""First-run and live-profile validation without Real input side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
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
    canonical_assets_installed: tuple[Path, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.missing_templates and not self.problems


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_canonical_real_assets(project_root: Path) -> tuple[Path, ...]:
    """Install missing canonical templates; never overwrite local calibration."""

    root = Path(project_root).resolve()
    asset_root = root / "real_assets" / "canonical_v1"
    manifest_path = asset_root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"CANONICAL_REAL_ASSET_MANIFEST_REQUIRED:{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise RuntimeError("CANONICAL_REAL_ASSET_SCHEMA_UNSUPPORTED")
    installed: list[Path] = []
    for entry in manifest.get("files", []):
        source = (asset_root / str(entry["source"])).resolve()
        target = (root / str(entry["target"])).resolve()
        if asset_root not in source.parents or root not in target.parents:
            raise RuntimeError("CANONICAL_REAL_ASSET_PATH_UNSAFE")
        expected = str(entry["sha256"]).lower()
        if not source.is_file() or _sha256(source) != expected:
            raise RuntimeError(f"CANONICAL_REAL_ASSET_SHA_MISMATCH:{source}")
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copyfile(source, temporary)
        if _sha256(temporary) != expected:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"CANONICAL_REAL_ASSET_COPY_MISMATCH:{target}")
        temporary.replace(target)
        installed.append(target)
    return tuple(installed)


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
    installed: tuple[Path, ...] = ()
    if initialize:
        config_path, created = initialize_local_config(root)
        installed = install_canonical_real_assets(root)
    else:
        config_path, created = root / "config.yaml", False
    if not config_path.is_file():
        return RealSetupReport(config_path, created, (), ("REAL_CONFIG_REQUIRED",), installed)

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
    return RealSetupReport(config_path, created, missing, tuple(problems), installed)


def print_report(report: RealSetupReport) -> None:
    print(f"REAL_CONFIG={report.config_path}")
    print(f"REAL_CONFIG_CREATED={'YES' if report.config_created else 'NO'}")
    for path in report.canonical_assets_installed:
        print(f"CANONICAL_REAL_ASSET_INSTALLED={path}")
    for problem in report.problems:
        print(f"REAL_SETUP_PROBLEM={problem}")
    for path in report.missing_templates:
        print(f"MISSING_REAL_TEMPLATE={path}")
    print(f"REAL_RUNTIME_READY={'YES' if report.ready else 'NO'}")
    if not report.ready:
        print("NEXT_STEP=Run FIRST_RUN_SETUP.cmd again; use CALIBRATE_REAL_GAME.cmd only if the canonical profile is incompatible")


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
