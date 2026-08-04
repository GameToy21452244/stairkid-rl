from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.config import AppConfig
from stair_agent.data.simulator_real_alignment import (
    collect_simulator_alignment_records,
    evaluate_simulator_real_alignment,
    load_jsonl_records,
)
from stair_agent.policies.simulator_teachers import SIMULATOR_TEACHER_PROFILES
from stair_agent.training.simulator_teacher_profile_gate import (
    spike_teacher_environment_config,
)


SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/data/real_alignment.py",
    "src/stair_agent/data/simulator_real_alignment.py",
    "src/stair_agent/envs/shaft_env.py",
    "src/stair_agent/simulator/generator.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/simulator_teacher_profile_gate.py",
    "scripts/audit_simulator_real_alignment.py",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _alignment_paths(directory: Path) -> list[Path]:
    paths = sorted(directory.glob("episode_*.alignment.jsonl"))
    if not paths:
        raise FileNotFoundError(f"找不到alignment packet：{directory}")
    return paths


def _packet_status(directory: Path) -> str:
    gate_path = directory / "teacher_real_game_micro_gate.json"
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    packet = payload.get("alignment_packet")
    if not isinstance(packet, dict):
        raise ValueError(f"{gate_path}缺少alignment_packet。")
    return str(packet.get("status", ""))


def _source_fingerprint(root: Path) -> dict[str, object]:
    combined = sha256()
    files: dict[str, str] = {}
    for relative in SOURCE_FILES:
        path = root / relative
        payload = path.read_bytes()
        digest = sha256(payload).hexdigest()
        files[relative] = digest
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(payload)
        combined.update(b"\0")
    return {"sha256": combined.hexdigest(), "files": files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--primary-real-dir",
        type=Path,
        default=Path("logs/teacher_real_micro_20260803_205952_924961"),
    )
    parser.add_argument(
        "--secondary-real-dir",
        type=Path,
        default=Path("logs/teacher_real_micro_20260803_205750_137469"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/simulator_real_alignment_audit_v3.json"),
    )
    parser.add_argument("--seed-start", type=int, default=8000)
    parser.add_argument("--episodes", type=int, default=30)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"拒絕覆寫既有稽核artifact：{args.output}")
    if args.seed_start == 6000 or (
        args.seed_start < 6100
        and args.seed_start + args.episodes - 1 >= 6000
    ):
        raise ValueError("Simulator診斷不得使用保留的6000..6099 fresh seeds。")
    if args.episodes != 30:
        raise ValueError("凍結protocol要求恰好30個Simulator診斷episodes。")

    root = Path(__file__).resolve().parents[1]
    primary_paths = _alignment_paths(args.primary_real_dir)
    secondary_paths = _alignment_paths(args.secondary_real_dir)
    primary = load_jsonl_records(primary_paths)
    secondary = load_jsonl_records(secondary_paths)
    primary_status = _packet_status(args.primary_real_dir)
    simulator_config = spike_teacher_environment_config()
    profile = SIMULATOR_TEACHER_PROFILES["departure_delayed"]
    app_config = AppConfig.load("config.yaml")
    seeds = list(range(args.seed_start, args.seed_start + args.episodes))
    simulator = collect_simulator_alignment_records(
        seeds,
        config=simulator_config,
        profile=profile,
        baseline_config=app_config.baseline,
    )
    result = evaluate_simulator_real_alignment(
        primary,
        secondary,
        simulator,
        primary_packet_status=primary_status,
        simulator_config=simulator_config,
    )
    result["experiment"] = "bounded-simulator-real-alignment-audit"
    result["protocol"] = {
        "path": "reports/SIMULATOR_REAL_ALIGNMENT_AUDIT_PROTOCOL.md",
        "frozen_before_execution": True,
        "simulator_seed_range": [seeds[0], seeds[-1]],
        "reserved_fresh_seeds_used": False,
        "simulator_episodes": len(seeds),
        "max_steps_per_episode": simulator_config.max_episode_steps,
        "profile": asdict(profile),
        "environment_config": asdict(simulator_config),
    }
    result["inputs"] = {
        "primary_real": {
            "directory": args.primary_real_dir.as_posix(),
            "packet_status": primary_status,
            "files": [
                {"path": path.as_posix(), "sha256": _sha256(path)}
                for path in primary_paths
            ],
        },
        "secondary_real": {
            "directory": args.secondary_real_dir.as_posix(),
            "packet_status": _packet_status(args.secondary_real_dir),
            "files": [
                {"path": path.as_posix(), "sha256": _sha256(path)}
                for path in secondary_paths
            ],
        },
    }
    result["source_fingerprint"] = _source_fingerprint(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"STATUS: {result['status']}")
    print(f"OUTPUT: {args.output.resolve()}")
    print(
        "MISSING KINDS:",
        result["platform_kinds"]["missing_from_simulator_distribution"],
    )
    print(
        "SUPPORT ALIAS:",
        result["primary_real"]["support_phase_alias_status"],
    )
    # A scientific Gate failure is a valid completed audit. Engineering or
    # schema failures still raise before this point and return non-zero.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
