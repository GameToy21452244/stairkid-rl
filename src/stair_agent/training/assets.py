"""Versioned external training assets, kept separate from Git source."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any, Mapping
from urllib.request import urlopen
import zipfile

from stair_agent.core.model_registry import sha256_file


ASSET_MANIFEST = Path("training_assets/manifest.json")
KNOWN_ASSET_SHA256 = {
    "r4_frozen_r1_bundle": "3b8e85d52d94b11cacf1466019558670791471a190d79b80ed18a62985b7f53e",
    "r4_seed117_r1_checkpoint": "d25dacc88b65563b392b18f3264747e665411116197268d5e5344972b4f1ca0a",
    "r4_seed142_r1_checkpoint": "4f105b391a3e6dbf6ae88a4ff85c2e229dac025f9ab7eadb48862db369995b59",
    "r4_seed117_bank_manifest": "1609cbe829ecd66de6bf47cc195bf2e7db60f2efdd8e40791d8b906472e62def",
    "r4_seed142_bank_manifest": "547f8ae66409799def75cbfab81c67f28188844cf93009ae0acf26fbc31bdc40",
}


class TrainingAssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrainingAsset:
    id: str
    filename: str
    sha256: str
    purpose: str
    required_for: tuple[str, ...]
    source: Mapping[str, Any]
    cache_path: Path
    required: bool


def _project_path(root: Path, value: str) -> Path:
    candidate = (root.resolve() / value).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise TrainingAssetError(f"TRAINING_ASSET_PATH_OUTSIDE_PROJECT:{value}")
    return candidate


def load_training_assets(project_root: Path) -> dict[str, TrainingAsset]:
    root = project_root.resolve()
    path = root / ASSET_MANIFEST
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingAssetError("TRAINING_ASSET_MANIFEST_INVALID") from exc
    if raw.get("schema_version") != 1 or not isinstance(raw.get("assets"), dict):
        raise TrainingAssetError("TRAINING_ASSET_MANIFEST_SCHEMA_INVALID")
    if set(raw["assets"]) != set(KNOWN_ASSET_SHA256):
        raise TrainingAssetError("TRAINING_ASSET_IDS_INVALID")
    result: dict[str, TrainingAsset] = {}
    for asset_id, item in raw["assets"].items():
        if item.get("asset_id") != asset_id:
            raise TrainingAssetError(f"TRAINING_ASSET_ID_MISMATCH:{asset_id}")
        if item.get("sha256") != KNOWN_ASSET_SHA256[asset_id]:
            raise TrainingAssetError(f"TRAINING_ASSET_PIN_MISMATCH:{asset_id}")
        required_for = tuple(item.get("required_for", []))
        if not required_for or any(value not in {"v3", "r4"} for value in required_for):
            raise TrainingAssetError(f"TRAINING_ASSET_TARGET_INVALID:{asset_id}")
        result[asset_id] = TrainingAsset(
            id=asset_id,
            filename=str(item["filename"]),
            sha256=str(item["sha256"]),
            purpose=str(item["purpose"]),
            required_for=required_for,
            source=dict(item["source"]),
            cache_path=_project_path(root, str(item["cache_path"])),
            required=bool(item["required"]),
        )
    return result


def verify_asset(asset: TrainingAsset, path: Path | None = None) -> Path:
    candidate = (path or asset.cache_path).resolve()
    if not candidate.is_file():
        raise TrainingAssetError(f"TRAINING_ASSET_REQUIRED:{asset.id}:{candidate}")
    actual = sha256_file(candidate)
    if actual != asset.sha256:
        raise TrainingAssetError(
            f"TRAINING_ASSET_SHA_MISMATCH:{asset.id}:{actual}!={asset.sha256}"
        )
    return candidate


def _copy_or_download(asset: TrainingAsset, source_dir: Path | None) -> Path:
    destination = asset.cache_path
    if destination.is_file():
        return verify_asset(asset)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    if temporary.exists():
        temporary.unlink()
    if source_dir is not None:
        source = (source_dir.resolve() / asset.filename).resolve()
        if not source.is_relative_to(source_dir.resolve()) or not source.is_file():
            raise TrainingAssetError(f"TRAINING_ASSET_SOURCE_FILE_MISSING:{source}")
        shutil.copyfile(source, temporary)
    else:
        url = asset.source.get("url")
        if not url:
            raise TrainingAssetError(
                f"TRAINING_ASSET_REMOTE_UNPUBLISHED:{asset.id}; use --source-dir"
            )
        with urlopen(str(url), timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != asset.sha256:
        temporary.unlink(missing_ok=True)
        raise TrainingAssetError(
            f"TRAINING_ASSET_SHA_MISMATCH:{asset.id}:{actual}!={asset.sha256}"
        )
    temporary.replace(destination)
    return verify_asset(asset)


def fetch_training_assets(
    project_root: Path,
    target_id: str,
    *,
    source_dir: Path | None = None,
) -> list[Path]:
    assets = load_training_assets(project_root)
    required = [
        asset
        for asset in assets.values()
        if target_id in asset.required_for and asset.required
    ]
    return [_copy_or_download(asset, source_dir) for asset in required]


def _safe_member(name: str) -> PurePosixPath:
    member = PurePosixPath(name)
    if member.is_absolute() or not member.parts or ".." in member.parts:
        raise TrainingAssetError(f"TRAINING_ASSET_UNSAFE_ZIP_MEMBER:{name}")
    return member


def stage_r4_bundle(project_root: Path) -> Path:
    """Validate and extract the historical bundle as data, never as source."""

    assets = load_training_assets(project_root)
    bundle = verify_asset(assets["r4_frozen_r1_bundle"])
    stage_root = (project_root.resolve() / "training_assets/cache/r4").resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise TrainingAssetError(f"R4_BUNDLE_CRC_FAIL:{bad}")
        for name in archive.namelist():
            member = _safe_member(name)
            destination = (stage_root / Path(*member.parts)).resolve()
            if not destination.is_relative_to(stage_root):
                raise TrainingAssetError(f"R4_BUNDLE_MEMBER_ESCAPES_CACHE:{name}")
            if name.endswith("/"):
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(name)
            if destination.is_file() and destination.read_bytes() == data:
                continue
            temporary = destination.with_suffix(destination.suffix + ".partial")
            temporary.write_bytes(data)
            temporary.replace(destination)
    checks = {
        "r4_seed117_r1_checkpoint": stage_root / "seed_117/checkpoints/v3_5_589824.zip",
        "r4_seed142_r1_checkpoint": stage_root / "seed_142/checkpoints/v3_5_589824.zip",
        "r4_seed117_bank_manifest": stage_root / "banks/seed_117/r1_targeted/manifest.json",
        "r4_seed142_bank_manifest": stage_root / "banks/seed_142/r1_targeted/manifest.json",
    }
    for asset_id, path in checks.items():
        verify_asset(assets[asset_id], path)
    return stage_root
