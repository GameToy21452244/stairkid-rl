from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _family(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("baseline_"):
        return "baseline"
    if name.startswith("reward_audit_"):
        return "reward_audit"
    if name.startswith("observations_"):
        return "observations"
    return "unknown"


def _inspect(path: Path, root: Path) -> dict[str, Any]:
    family = _family(path)
    rows = 0
    json_errors = 0
    dimensions: set[int] = set()
    actions: Counter[str] = Counter()
    keys: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                json_errors += 1
                continue
            if not isinstance(payload, dict):
                json_errors += 1
                continue
            rows += 1
            keys.update(payload)
            features = payload.get("features")
            if isinstance(features, list):
                dimensions.add(len(features))
            if "action" in payload:
                actions[str(payload["action"])] += 1
    reasons = [
        "missing_schema_version",
        "missing_episode_id",
        "missing_action_timestamps",
        "missing_observation_schema_version",
        "missing_reward_version",
    ]
    if family == "observations":
        reasons += ["missing_action", "missing_next_observation", "missing_reward"]
    else:
        reasons.append("unverified_policy_source")
    if "next_observation" not in keys:
        reasons.append("missing_next_observation")
    if "reward_components" not in keys:
        reasons.append("missing_reward_components")
    if json_errors:
        reasons.append("invalid_json")
    return {
        "path": path.relative_to(root).as_posix(),
        "family": family,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "rows": rows,
        "json_errors": json_errors,
        "top_level_keys": sorted(keys),
        "feature_dimensions": sorted(dimensions),
        "action_counts": dict(sorted(actions.items())),
        "eligible_for_bc": False,
        "eligible_for_dqn": False,
        "quarantine": True,
        "reasons": sorted(set(reasons)),
    }


def build_quarantine_manifest(source_root: str | Path) -> dict[str, Any]:
    root = Path(source_root)
    if not root.is_dir():
        raise FileNotFoundError(f"找不到 legacy data 目錄：{root}")
    files = [_inspect(path, root) for path in sorted(root.rglob("*.jsonl"))]
    return {
        "schema_version": "legacy-quarantine-manifest-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root.resolve()),
        "file_count": len(files),
        "total_rows": sum(item["rows"] for item in files),
        "eligible_for_bc_files": 0,
        "eligible_for_dqn_files": 0,
        "files": files,
    }
