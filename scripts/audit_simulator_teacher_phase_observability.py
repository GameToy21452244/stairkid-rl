from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import _common  # noqa: F401,E402

from stair_agent.data.simulator_phase_audit import (
    summarize_phase_observability,
)
from stair_agent.policies.simulator_teachers import (
    SIMULATOR_TEACHER_PROFILES,
    TeacherObservable,
)
from stair_agent.training.simulator_teacher_profile_gate import (
    SAME_SEED_COUNT,
    SAME_SEED_START,
    evaluate_simulator_teacher_profile,
)


SCHEMA_VERSION = "simulator-teacher-phase-observability-audit-v1"
BASE_PROFILE = "departure_delayed"
SHADOW_PROFILE = "departure_delayed_launch_handoff"
SOURCE_FILES = (
    "src/stair_agent/baseline_policy.py",
    "src/stair_agent/data/simulator_phase_audit.py",
    "src/stair_agent/envs/shaft_env.py",
    "src/stair_agent/policies/simulator_teachers.py",
    "src/stair_agent/training/simulator_teacher_profile_gate.py",
    "scripts/audit_simulator_teacher_phase_observability.py",
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


def _outcome_delta(base: str, candidate: str) -> str:
    if base == "target_reached" and candidate != "target_reached":
        return "regressed"
    if base != "target_reached" and candidate == "target_reached":
        return "improved"
    return "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--launch-artifact",
        type=Path,
        default=Path(
            "artifacts/simulator_teacher_launch_handoff_gate_v1.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/simulator_teacher_phase_observability_audit_v1.json"
        ),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = Path(__file__).resolve().parents[1]
    source = json.loads(args.launch_artifact.read_text(encoding="utf-8"))
    if source["status"] != "FAIL_STOP_LAUNCH_HANDOFF_SAME_SEED":
        raise RuntimeError("Launch-handoff來源artifact狀態不符。")
    if source["fresh_protocol"]["executed"]:
        raise RuntimeError("來源Launch-handoff Gate不應使用fresh seeds。")

    source_base = source["base"]
    source_candidate = source["candidate"]
    base_outcomes = {
        seed: str(details["outcome"])
        for seed, details in source_base["analysis"]["episode_details"].items()
    }
    candidate_outcomes = {
        seed: str(details["outcome"])
        for seed, details in source_candidate["analysis"]["episode_details"].items()
    }
    expected_divergence = source_candidate[
        "comparison_to_delayed_base"
    ]["first_action_divergence_by_seed"]

    shadow_teachers: dict[int, TeacherObservable] = {}
    diverged: set[int] = set()
    landing_recency: dict[int, int | None] = {}
    first_divergences: list[dict[str, object]] = []
    all_samples: list[dict[str, object]] = []

    def observe(seed, step, observation, base_decision, env) -> None:
        if seed not in shadow_teachers:
            shadow_teachers[seed] = TeacherObservable(
                verified=True,
                profile=SIMULATOR_TEACHER_PROFILES[SHADOW_PROFILE],
            )
            landing_recency[seed] = None
        event_types = {
            str(event.get("type", "")) for event in observation.events
        }
        landed_event = bool(
            event_types & {"landed", "floor_descended"}
        )
        if landed_event:
            landing_recency[seed] = 0
        elif landing_recency[seed] is not None:
            landing_recency[seed] = int(landing_recency[seed]) + 1

        player = observation.player or {}
        player_x = float(player.get("center_x", 0.0))
        nearest = observation.nearest_platform or {}
        nearest_box = nearest.get("box") or {}
        left = float(nearest_box.get("left", 0.0))
        width = float(nearest_box.get("width", 0.0))
        right = left + width
        gap_raw = nearest.get("vertical_gap")
        gap = None if gap_raw is None else float(gap_raw)
        within_x = width > 0.0 and left <= player_x <= right
        support = bool(
            gap is not None and 0.0 <= gap <= 12.0 and within_x
        )
        edge_distance = (
            min(player_x - left, right - player_x)
            if width > 0.0
            else None
        )
        nearest_id_raw = nearest.get("track_id")
        nearest_id = (
            None if nearest_id_raw is None else int(nearest_id_raw)
        )
        physical_vy = float(env.simulator.player.body.velocity.y)
        recency = landing_recency[seed]
        if landed_event:
            privileged_phase = "post_collision_bounce"
        elif recency is not None and recency <= 3 and physical_vy > 0.0:
            privileged_phase = "post_bounce_launch"
        elif physical_vy > 0.0:
            privileged_phase = "rising_airborne"
        else:
            privileged_phase = "falling_airborne"
        sample = {
            "seed": seed,
            "step": step,
            "motion": str(player.get("motion", "")),
            "velocity_x": float(player.get("velocity_x", 0.0)),
            "velocity_y": float(player.get("velocity_y", 0.0)),
            "player_x": player_x,
            "player_y": float(player.get("center_y", 0.0)),
            "nearest_gap": gap,
            "nearest_platform_kind": (
                None if not nearest else str(nearest.get("kind", ""))
            ),
            "within_nearest_x": within_x,
            "edge_distance": edge_distance,
            "support_heuristic": support,
            "landed_event": landed_event,
            "floor_descended_event": "floor_descended" in event_types,
            "steps_since_landing_event": recency,
            "visible_platform_count": len(observation.platforms),
            "health_segments": int(
                (observation.health or {}).get("segments") or 0
            ),
            "base_action": int(base_decision.action),
            "base_reason": base_decision.reason,
            "base_target_kind": base_decision.target_platform_kind,
            "privileged_diagnostic": {
                "phase_label": privileged_phase,
                "physical_velocity_y": physical_vy,
                "deepest_floor": int(env.simulator.deepest_floor),
                "last_landed_floor": env.simulator.last_landed_floor,
                "nearest_is_last_landed": (
                    nearest_id is not None
                    and nearest_id == env.simulator.last_landed_floor
                ),
            },
        }
        all_samples.append(sample)
        if seed in diverged:
            return
        shadow = shadow_teachers[seed].choose(observation)
        if int(shadow.action) != int(base_decision.action):
            diverged.add(seed)
            first = dict(sample)
            first["shadow_action"] = int(shadow.action)
            first["shadow_reason"] = shadow.reason
            first["base_outcome"] = base_outcomes[str(seed)]
            first["candidate_outcome"] = candidate_outcomes[str(seed)]
            first["intervention_outcome"] = _outcome_delta(
                base_outcomes[str(seed)],
                candidate_outcomes[str(seed)],
            )
            first_divergences.append(first)

    seeds = range(SAME_SEED_START, SAME_SEED_START + SAME_SEED_COUNT)
    reproduced = evaluate_simulator_teacher_profile(
        SIMULATOR_TEACHER_PROFILES[BASE_PROFILE],
        seeds,
        decision_observer=observe,
    )
    if reproduced["analysis"]["sha256"] != source_base["analysis"]["sha256"]:
        raise RuntimeError("Phase audit未重現delayed2 base trace。")
    if reproduced["performance"] != source_base["performance"]:
        raise RuntimeError("Phase audit未重現delayed2 base performance。")
    observed_steps = {
        str(row["seed"]): int(row["step"]) for row in first_divergences
    }
    if observed_steps != {
        str(seed): int(step)
        for seed, step in expected_divergence.items()
    }:
        raise RuntimeError("Shadow first-divergence steps未重現來源artifact。")
    for sample in all_samples:
        sample["base_outcome"] = base_outcomes[str(sample["seed"])]

    audit = summarize_phase_observability(
        first_divergences,
        all_samples,
        expected_episodes=SAME_SEED_COUNT,
    )
    phase_by_outcome: dict[str, Counter[str]] = defaultdict(Counter)
    nearest_last_by_outcome: dict[str, Counter[str]] = defaultdict(Counter)
    for row in first_divergences:
        outcome = str(row["intervention_outcome"])
        diagnostic = row["privileged_diagnostic"]
        phase_by_outcome[outcome][str(diagnostic["phase_label"])] += 1
        nearest_last_by_outcome[outcome][
            str(bool(diagnostic["nearest_is_last_landed"]))
        ] += 1

    output = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "Simulator-Teacher-phase-observability-audit",
        "status": audit["status"],
        "training_started": False,
        "controller_modified": False,
        "real_game_started": False,
        "fresh_seeds_used": False,
        "formal_dataset_v2_generated": False,
        "source_launch_artifact": {
            "path": args.launch_artifact.as_posix(),
            "sha256": _sha256(args.launch_artifact),
            "status": source["status"],
        },
        "protocol": {
            "profile": BASE_PROFILE,
            "shadow_profile": SHADOW_PROFILE,
            "seed_range": [
                SAME_SEED_START,
                SAME_SEED_START + SAME_SEED_COUNT - 1,
            ],
            "base_trace_reproduced": True,
            "first_divergence_steps_reproduced": True,
            "privileged_fields_are_diagnostic_labels_only": True,
        },
        "source_fingerprint": _source_fingerprint(root),
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "audit": audit,
        "privileged_phase_by_intervention_outcome": {
            outcome: dict(sorted(counts.items()))
            for outcome, counts in sorted(phase_by_outcome.items())
        },
        "nearest_is_last_landed_by_intervention_outcome": {
            outcome: dict(sorted(counts.items()))
            for outcome, counts in sorted(nearest_last_by_outcome.items())
        },
        "first_divergences": sorted(
            first_divergences,
            key=lambda row: int(row["seed"]),
        ),
        "next_stage": (
            "DESIGN_ONE_CAUSAL_PHASE_CANDIDATE"
            if audit["passed"]
            else "STOP_AND_REVIEW_OBSERVATION_SCHEMA"
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
                "first_divergence_outcomes": audit[
                    "first_divergence_outcomes"
                ],
                "unique_phase_signatures": audit[
                    "unique_phase_signatures"
                ],
                "signature_conflicts": len(
                    audit["improved_regressed_signature_conflicts"]
                ),
                "support_overlap": audit["support_overlap"],
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
