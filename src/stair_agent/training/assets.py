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
    """Validate and extract the historical bundle as data, never as source.

    The externally managed integrity gate is the bundle SHA. Embedded
    checkpoint and bank identities are validated structurally and against one
    another after extraction instead of being duplicated as user-facing pins.
    """

    assets = load_training_assets(project_root)
    bundle = verify_asset(assets["r4_frozen_r1_bundle"])
    stage_root = (project_root.resolve() / "training_assets/cache/r4").resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise TrainingAssetError(f"R4_BUNDLE_CRC_FAIL:{bad}")
        try:
            bundle_manifest = json.loads(
                archive.read("FROZEN_R1_BUNDLE_MANIFEST.json")
            )
        except (KeyError, json.JSONDecodeError) as exc:
            raise TrainingAssetError("R4_BUNDLE_MANIFEST_INVALID") from exc
        expected_bundle_contract = {
            "schema_version": "stairkid-v3-5-r4-frozen-r1-input-v1",
            "purpose": "R4_FROZEN_R1_AND_TARGETED_BANK_REUSE_ONLY",
            "policy_seeds": [117, 142],
            "r1_timesteps": 589824,
            "r1_retraining_forbidden": True,
            "bank_recollection_forbidden": True,
            "bank_schema_version": "v3-5-targeted-safety-bank-r3-corrected-flipping-v1",
            "bank_counts_per_seed": {
                "landing": 20,
                "spike": 20,
                "top": 8,
                "success": 48,
            },
        }
        for key, expected in expected_bundle_contract.items():
            if bundle_manifest.get(key) != expected:
                raise TrainingAssetError(f"R4_BUNDLE_CONTRACT_MISMATCH:{key}")
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
    from stair_agent.v3_5_curriculum import validate_v35_targeted_bank

    for seed in (117, 142):
        checkpoint = stage_root / f"seed_{seed}/checkpoints/v3_5_589824.zip"
        checkpoint_metadata = checkpoint.with_suffix(".json")
        bank_dir = stage_root / f"banks/seed_{seed}/r1_targeted"
        bank_manifest = bank_dir / "manifest.json"
        if not checkpoint.is_file() or not checkpoint_metadata.is_file():
            raise TrainingAssetError(f"R4_BUNDLE_CHECKPOINT_MISSING:{seed}")
        if not bank_manifest.is_file():
            raise TrainingAssetError(f"R4_BUNDLE_BANK_MISSING:{seed}")
        try:
            checkpoint_row = json.loads(checkpoint_metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TrainingAssetError(f"R4_CHECKPOINT_METADATA_INVALID:{seed}") from exc
        checkpoint_sha = sha256_file(checkpoint)
        expected_checkpoint_path = f"seed_{seed}/checkpoints/v3_5_589824.zip"
        if (
            checkpoint_row.get("policy_seed") != seed
            or checkpoint_row.get("num_timesteps") != 589824
            or checkpoint_row.get("target_timesteps") != 589824
            or checkpoint_row.get("path") != expected_checkpoint_path
            or checkpoint_row.get("sha256") != checkpoint_sha
        ):
            raise TrainingAssetError(f"R4_CHECKPOINT_PAIRING_INVALID:{seed}")
        try:
            with zipfile.ZipFile(checkpoint) as checkpoint_archive:
                if checkpoint_archive.testzip() is not None:
                    raise TrainingAssetError(f"R4_CHECKPOINT_CRC_FAIL:{seed}")
        except zipfile.BadZipFile as exc:
            raise TrainingAssetError(f"R4_CHECKPOINT_ZIP_INVALID:{seed}") from exc
        try:
            validate_v35_targeted_bank(
                bank_dir,
                bank_manifest,
                expected_policy_seed=seed,
                expected_source_sha256=checkpoint_sha,
                expected_source_timesteps=589824,
            )
        except (OSError, ValueError) as exc:
            raise TrainingAssetError(f"R4_BANK_STRUCTURE_INVALID:{seed}:{exc}") from exc
    return stage_root
