from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import _common  # noqa: F401,E402

from stair_agent.config import BaselineConfig
from stair_agent.data.simulator_observation_schema_probe import (
    summarize_observation_schema_probe,
)
from stair_agent.observation import GameObservation
from stair_agent.policies.simulator_teachers import (
    SIMULATOR_TEACHER_PROFILES,
    TeacherDecision,
    TeacherObservable,
)
from stair_agent.training.p41_sequence import CausalActionState
from stair_agent.training.simulator_teacher_profile_gate import (
    evaluate_simulator_teacher_profile,
)


SCHEMA_VERSION = "simulator-observation-schema-probe-v1"
BASE_PROFILE = "departure_delayed"
SHADOW_PROFILE = "departure_delayed_launch_handoff"
DEVELOPMENT_SEEDS = tuple(range(7000, 7200))
VALIDATION_SEEDS = tuple(range(7200, 7300))
TEST_SEEDS = tuple(range(7300, 7400))
ALL_SEEDS = DEVELOPMENT_SEEDS + VALIDATION_SEEDS + TEST_SEEDS
SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/data/simulator_observation_schema_probe.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/training/p41_sequence.py",
    "src/stair_agent/training/simulator_teacher_profile_gate.py",
    "scripts/probe_simulator_teacher_observation_schema.py",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprint(root: Path) -> dict[str, object]:
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _split(seed: int) -> str:
    if seed in DEVELOPMENT_SEEDS:
        return "development"
    if seed in VALIDATION_SEEDS:
        return "validation"
    if seed in TEST_SEEDS:
        return "test"
    raise ValueError(f"seed未凍結於schema probe：{seed}")


def _outcome_delta(base: str, candidate: str) -> str:
    if base == "target_reached" and candidate != "target_reached":
        return "regressed"
    if base != "target_reached" and candidate == "target_reached":
        return "improved"
    return "unchanged"


def _target_geometry(
    observation: GameObservation,
    decision: TeacherDecision,
    *,
    margin: float,
) -> dict[str, object]:
    player = observation.player or {}
    player_x = float(player.get("center_x", 0.0))
    player_y = float(player.get("center_y", 0.0))
    target_present = decision.target_platform_id is not None
    matched = None
    if target_present:
        for platform in observation.platforms:
            track_id = platform.get("track_id")
            if track_id is not None and int(track_id) == int(
                decision.target_platform_id
            ):
                matched = platform
                break
    if matched is None:
        return {
            "target_present": target_present,
            "target_matched": False,
            "target_signed_offset": decision.target_signed_offset,
            "target_center_delta": None,
            "target_top_delta": None,
            "target_safe_left_delta": None,
            "target_safe_right_delta": None,
            "target_platform_kind": decision.target_platform_kind,
        }
    box = matched.get("box") or {}
    left = float(box.get("left", 0.0))
    width = float(box.get("width", 0.0))
    top = float(box.get("top", 0.0))
    effective_margin = min(float(margin), max(0.0, width / 3.0))
    safe_left = left + effective_margin
    safe_right = left + width - effective_margin
    return {
        "target_present": True,
        "target_matched": True,
        "target_signed_offset": decision.target_signed_offset,
        "target_center_delta": left + width / 2.0 - player_x,
        "target_top_delta": top - player_y,
        "target_safe_left_delta": safe_left - player_x,
        "target_safe_right_delta": safe_right - player_x,
        "target_platform_kind": str(matched.get("kind", "")) or None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase-artifact",
        type=Path,
        default=Path(
            "artifacts/simulator_teacher_phase_observability_audit_v1.json"
        ),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path(
            "reports/SIMULATOR_OBSERVATION_SCHEMA_PROBE_PROTOCOL.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/simulator_teacher_observation_schema_probe_v1.json"
        ),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    phase_source = json.loads(args.phase_artifact.read_text(encoding="utf-8"))
    if phase_source["status"] != "INSUFFICIENT_EVIDENCE_STOP_PHASE_MODEL":
        raise RuntimeError("Phase audit來源狀態不符。")
    if not args.protocol.exists():
        raise FileNotFoundError(args.protocol)

    shadow_teachers: dict[int, TeacherObservable] = {}
    action_states: dict[int, CausalActionState] = {}
    landing_recency: dict[int, int | None] = {}
    diverged: set[int] = set()
    first_divergences: list[dict[str, object]] = []
    baseline_config = BaselineConfig()

    def observe(seed, step, observation, base_decision, _env) -> None:
        if seed not in shadow_teachers:
            shadow_teachers[seed] = TeacherObservable(
                verified=True,
                profile=SIMULATOR_TEACHER_PROFILES[SHADOW_PROFILE],
            )
            action_states[seed] = CausalActionState()
            landing_recency[seed] = None
        event_types = {
            str(event.get("type", "")) for event in observation.events
        }
        landed = bool(event_types & {"landed", "floor_descended"})
        if landed:
            landing_recency[seed] = 0
        elif landing_recency[seed] is not None:
            landing_recency[seed] = int(landing_recency[seed]) + 1

        causal_state = action_states[seed].snapshot().tolist()
        if seed not in diverged:
            shadow = shadow_teachers[seed].choose(observation)
            if int(shadow.action) != int(base_decision.action):
                diverged.add(seed)
                player = observation.player or {}
                player_x = float(player.get("center_x", 0.0))
                nearest = observation.nearest_platform or {}
                nearest_box = nearest.get("box") or {}
                nearest_left = float(nearest_box.get("left", 0.0))
                nearest_width = float(nearest_box.get("width", 0.0))
                nearest_right = nearest_left + nearest_width
                gap_raw = nearest.get("vertical_gap")
                gap = None if gap_raw is None else float(gap_raw)
                within_x = (
                    nearest_width > 0.0
                    and nearest_left <= player_x <= nearest_right
                )
                edge_distance = (
                    min(player_x - nearest_left, nearest_right - player_x)
                    if nearest_width > 0.0
                    else None
                )
                sample = {
                    "seed": int(seed),
                    "split": _split(int(seed)),
                    "step": int(step),
                    "motion": str(player.get("motion", "")),
                    "velocity_x": float(player.get("velocity_x", 0.0)),
                    "velocity_y": float(player.get("velocity_y", 0.0)),
                    "nearest_gap": gap,
                    "nearest_platform_kind": (
                        None if not nearest else str(nearest.get("kind", ""))
                    ),
                    "support_heuristic": bool(
                        gap is not None and 0.0 <= gap <= 12.0 and within_x
                    ),
                    "landed_event": landed,
                    "floor_descended_event": "floor_descended" in event_types,
                    "steps_since_landing_event": landing_recency[seed],
                    "edge_distance": edge_distance,
                    "visible_platform_count": len(observation.platforms),
                    "health_segments": int(
                        (observation.health or {}).get("segments") or 0
                    ),
                    "base_action": int(base_decision.action),
                    "base_reason": base_decision.reason,
                    "shadow_action": int(shadow.action),
                    "shadow_reason": shadow.reason,
                    "causal_action_state": causal_state,
                    **_target_geometry(
                        observation,
                        base_decision,
                        margin=baseline_config.landing_margin_pixels,
                    ),
                }
                first_divergences.append(sample)
        action_states[seed].update(int(base_decision.action))

    candidate = evaluate_simulator_teacher_profile(
        SIMULATOR_TEACHER_PROFILES[SHADOW_PROFILE],
        ALL_SEEDS,
    )
    base = evaluate_simulator_teacher_profile(
        SIMULATOR_TEACHER_PROFILES[BASE_PROFILE],
        ALL_SEEDS,
        decision_observer=observe,
    )
    base_outcomes = {
        seed: str(details["outcome"])
        for seed, details in base["analysis"]["episode_details"].items()
    }
    candidate_outcomes = {
        seed: str(details["outcome"])
        for seed, details in candidate["analysis"]["episode_details"].items()
    }
    for row in first_divergences:
        seed = str(row["seed"])
        row["base_outcome"] = base_outcomes[seed]
        row["candidate_outcome"] = candidate_outcomes[seed]
        row["intervention_outcome"] = _outcome_delta(
            base_outcomes[seed],
            candidate_outcomes[seed],
        )
    first_divergences.sort(key=lambda row: int(row["seed"]))
    audit = summarize_observation_schema_probe(
        first_divergences,
        expected_episodes=len(ALL_SEEDS),
    )
    output = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "simulator-teacher-observation-schema-probe",
        "status": audit["status"],
        "training_started": False,
        "controller_modified": False,
        "real_game_started": False,
        "fresh_reliability_seeds_used": False,
        "formal_dataset_v2_generated": False,
        "source_phase_artifact": {
            "path": args.phase_artifact.as_posix(),
            "sha256": _sha256(args.phase_artifact),
            "status": phase_source["status"],
        },
        "frozen_protocol": {
            "path": args.protocol.as_posix(),
            "sha256": _sha256(args.protocol),
            "development_seed_range": [7000, 7199],
            "validation_seed_range": [7200, 7299],
            "test_seed_range": [7300, 7399],
            "test_evaluated_once": True,
            "reserved_fresh_seed_range": [6000, 6099],
            "reserved_fresh_seeds_used": False,
            "base_profile": BASE_PROFILE,
            "shadow_profile": SHADOW_PROFILE,
            "raw_identity_exported": False,
            "privileged_feature_used": False,
        },
        "source_fingerprint": _source_fingerprint(root),
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "base": {
            "profile": base["profile"],
            "performance": base["performance"],
            "trace_sha256": base["analysis"]["sha256"],
        },
        "counterfactual": {
            "profile": candidate["profile"],
            "performance": candidate["performance"],
            "trace_sha256": candidate["analysis"]["sha256"],
        },
        "audit": audit,
        "first_divergences": first_divergences,
        "next_stage": (
            "DESIGN_ONE_TARGET_CONDITIONED_TEACHER_CANDIDATE"
            if audit["passed"]
            else "STOP_AND_COLLECT_TARGETED_REAL_ALIGNMENT_PACKET"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "outcomes": audit["outcomes"],
                "outcomes_by_split": audit["outcomes_by_split"],
                "combined_validation": audit["metrics"]["combined"][
                    "validation"
                ],
                "combined_test": audit["metrics"]["combined"]["test"],
                "next_stage": output["next_stage"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
