"""Fetch canonical read-only model assets with no fallback behavior."""

from __future__ import annotations

from pathlib import Path
import shutil
from urllib.request import urlopen

from stair_agent.core.model_registry import (
    CanonicalModel,
    load_model_registry,
    sha256_file,
)


class ModelFetchError(RuntimeError):
    pass


def fetch_model(
    project_root: Path,
    model_id: str,
    *,
    source_dir: Path | None = None,
) -> Path:
    registry = load_model_registry(project_root)
    if model_id not in registry:
        raise ModelFetchError(f"UNKNOWN_MODEL_ID:{model_id}")
    spec: CanonicalModel = registry[model_id]
    if spec.asset_path.is_file():
        actual = sha256_file(spec.asset_path)
        if actual != spec.sha256:
            raise ModelFetchError(f"MODEL_CACHE_SHA_MISMATCH:{model_id}:{actual}")
        return spec.asset_path
    spec.asset_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = spec.asset_path.with_suffix(spec.asset_path.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    if source_dir is not None:
        source = (source_dir.resolve() / spec.asset_path.name).resolve()
        if not source.is_relative_to(source_dir.resolve()) or not source.is_file():
            raise ModelFetchError(f"MODEL_SOURCE_FILE_MISSING:{source}")
        shutil.copyfile(source, temporary)
    else:
        url = spec.metadata.get("release_url")
        if not url:
            raise ModelFetchError(
                f"MODEL_RELEASE_ASSET_UNPUBLISHED:{model_id}; use --source-dir"
            )
        with urlopen(str(url), timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != spec.sha256:
        temporary.unlink(missing_ok=True)
        raise ModelFetchError(f"MODEL_DOWNLOAD_SHA_MISMATCH:{model_id}:{actual}")
    temporary.replace(spec.asset_path)
    return spec.asset_path
