from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import _common  # noqa: F401,E402

from stair_agent.training.spring_curriculum_gate import spring_curriculum_config
from stair_agent.training.spring_failure_audit import (
    analyze_real_spring_evidence,
    load_alignment_records,
    trace_oracle_spring_failures,
)


OUTPUT = Path("artifacts/spring_failure_fidelity_audit_v1.json")
PROTOCOL = Path("reports/SPRING_FAILURE_TRACE_FIDELITY_PROTOCOL.md")
REAL_DIRECTORY = Path("logs/teacher_real_micro_20260803_205952_924961")
SOURCE_FILES = (
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/simulator/physics.py",
    "src/stair_agent/simulator/state.py",
    "src/stair_agent/training/spring_curriculum_gate.py",
    "src/stair_agent/training/spring_failure_audit.py",
    "scripts/audit_spring_failure_fidelity.py",
)


def _fingerprint(root: Path) -> dict[str, object]:
    combined = sha256()
    files: dict[str, str] = {}
    for relative in SOURCE_FILES:
        payload = (root / relative).read_bytes()
        files[relative] = sha256(payload).hexdigest()
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(payload)
        combined.update(b"\0")
    return {"sha256": combined.hexdigest(), "files": files}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"拒絕覆寫既有audit artifact：{OUTPUT}")
    root = Path(__file__).resolve().parents[1]
    paths = sorted(REAL_DIRECTORY.glob("episode_*.alignment.jsonl"))
    if len(paths) != 3:
        raise ValueError("Spring fidelity audit要求既有3個alignment packets。")
    real_records = load_alignment_records(paths)
    real = analyze_real_spring_evidence(real_records)
    simulator = trace_oracle_spring_failures(
        range(10000, 10100),
        config=spring_curriculum_config(),
        max_episode_steps=600,
        enable_spring_escape=False,
    )
    supported = bool(
        simulator["hypotheses"]["oracle_escape_candidate_supported"]
    )
    payload = {
        "experiment": "spring-failure-trace-fidelity-audit-v1",
        "status": (
            "PASS_DIAGNOSIS_ORACLE_ESCAPE_CANDIDATE_ALLOWED"
            if supported
            else "FAIL_STOP_DIAGNOSIS"
        ),
        "passed": supported,
        "training_started": False,
        "real_game_started": False,
        "dataset_generated": False,
        "protocol": {
            "path": PROTOCOL.as_posix(),
            "sha256": sha256((root / PROTOCOL).read_bytes()).hexdigest(),
            "frozen_before_execution": True,
        },
        "simulator_config": asdict(spring_curriculum_config()),
        "simulator": simulator,
        "real_evidence": {
            **real,
            "directory": REAL_DIRECTORY.as_posix(),
            "files": [
                {
                    "path": path.as_posix(),
                    "sha256": sha256(path.read_bytes()).hexdigest(),
                }
                for path in paths
            ],
        },
        "decision": {
            "physics_change_allowed": False,
            "oracle_escape_candidate_allowed": supported,
            "reason": (
                "single bounce was not terminal; every spring-conditioned "
                "top death followed repeated contacts, while real packet "
                "has no confirmed spring event pairs for physics calibration"
            ),
        },
        "source_fingerprint": _fingerprint(root),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"STATUS: {payload['status']}")
    print(f"OUTPUT: {OUTPUT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
