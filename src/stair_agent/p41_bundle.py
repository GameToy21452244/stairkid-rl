"""Create a Colab bundle containing the exact frozen P4.1 dataset."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile


BUNDLE_ROOT = "ai-stair-agent"
LOCAL_ONLY_NAMES = {"config.yaml"}
FORBIDDEN_SUFFIXES = {".exe", ".mp4", ".avi", ".pt", ".pth", ".onnx", ".zip"}


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"bundle source 超出 repository：{resolved}") from exc


def _allowed_source(relative: Path) -> bool:
    if relative.name in LOCAL_ONLY_NAMES:
        return False
    if any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in relative.parts):
        return False
    if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        return False
    if relative.suffix.lower() == ".jsonl":
        return False
    return True


def create_p41_bundle(
    *,
    repo_root: str | Path,
    target: str | Path,
    source_files: Iterable[str | Path],
    dataset_path: str | Path,
    git_commit: str,
    dirty: bool,
) -> dict[str, object]:
    root = Path(repo_root).resolve()
    output = Path(target).resolve()
    if output.exists():
        raise FileExistsError(output)
    dataset = Path(dataset_path).resolve()
    dataset_relative = _inside(dataset, root)
    if dataset_relative.as_posix() != "artifacts/spike_teacher_dataset_v1.jsonl":
        raise ValueError("P4.1 bundle 只允許既定 Spike Teacher Dataset v1 路徑。")
    manifest_path = root / "artifacts" / "p41_experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_digest = str(manifest.get("dataset", {}).get("sha256", ""))
    actual_digest = sha256(dataset.read_bytes()).hexdigest()
    if expected_digest != actual_digest:
        raise ValueError(
            "frozen dataset SHA-256 與 P4.1 manifest 不一致；拒絕打包。"
        )

    selected: dict[str, Path] = {}
    for value in source_files:
        path = Path(value).resolve()
        if not path.is_file():
            continue
        relative = _inside(path, root)
        if _allowed_source(relative):
            selected[relative.as_posix()] = path
    selected[dataset_relative.as_posix()] = dataset
    required = {
        "artifacts/p41_experiment_manifest.json",
        "scripts/run_p41_ablation.py",
        "notebooks/ns_shaft_colab.ipynb",
        "pyproject.toml",
    }
    missing = sorted(required - set(selected))
    if missing:
        raise ValueError(f"P4.1 bundle 缺少必要 source：{missing}")

    output.parent.mkdir(parents=True, exist_ok=True)
    bundle_manifest = {
        "bundle": "ns-shaft-p41-colab-v1",
        "git_commit": git_commit,
        "dirty": bool(dirty),
        "dataset_path": dataset_relative.as_posix(),
        "dataset_sha256": actual_digest,
        "source_file_count": len(selected) - 1,
        "includes_frozen_dataset": True,
        "excludes_local_config_and_real_game_media": True,
    }
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, path in sorted(selected.items()):
            archive.write(path, f"{BUNDLE_ROOT}/{relative}")
        archive.writestr(
            f"{BUNDLE_ROOT}/p41_bundle_manifest.json",
            json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return {
        **bundle_manifest,
        "path": str(output),
        "bytes": output.stat().st_size,
        "archive_sha256": sha256(output.read_bytes()).hexdigest(),
    }


__all__ = ["create_p41_bundle"]
