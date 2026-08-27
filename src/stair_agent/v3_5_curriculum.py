from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from .envs.fidelity_v3_5 import V35_CORRECTED_PHYSICS_COMMIT, FidelityV35Env, make_fidelity_v3_5_env

V35_BANK_SCHEMA = "v3-5-targeted-safety-bank-r3-corrected-flipping-v1"
V35_BANK_LINEAGE = "fresh-v3-5-safety-refinement-r3-corrected-flipping"
V35_RISK_COUNTS = {"landing": 20, "spike": 20, "top": 8}
V35_SUCCESS_COUNT = 48
V35_LOOKBACK = {"landing": 3, "spike": 5, "top": 3}
V35_RUNTIME_SCHEDULE = ("ordinary", "ordinary", "failure", "success")
V35_RUNTIME_SCHEDULE_SEMANTICS = "fixed_vector_lane_timestep_quota"
V35_FAILURE_HORIZON_STEPS = 12
V35_SUCCESS_HORIZON_STEPS = 8
V35_RISK_RUNTIME_CYCLE = ("landing", "spike", "landing", "spike", "top")
V35_SUCCESS_MIN_FLOOR = 5
V35_PER_EPISODE_CAPS = {"landing": 1, "spike": 1, "top": 1, "success": 1}
V35_LANDING_RISK_DEFINITION = "edge_landing_first_with_miss_or_bottom_fallback"
V35_SPIKE_PRIORITY_HEALTH_BASIS = "first_damage_event_per_episode"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _history_snapshot(
    history: deque[tuple[int, dict[str, Any]]],
    lookback: int,
) -> tuple[int, dict[str, Any]]:
    rows = list(history)
    if not rows:
        raise RuntimeError("V35_BANK_HISTORY_EMPTY")
    index = max(0, len(rows) - 1 - int(lookback))
    return rows[index]


def _entry_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"landing": 0, "spike": 0, "top": 0, "success": 0}
    for item in entries:
        category = str(item.get("category"))
        if category in counts:
            counts[category] += 1
    return counts


def _unique_episode_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for category in ("landing", "spike", "top", "success"):
        result[category] = len(
            {
                int(item["source_episode_seed"])
                for item in entries
                if item.get("category") == category
            }
        )
    return result


def is_v35_landing_risk_event(
    events: set[str],
    terminal_reason: str | None = None,
    collision_diagnostic: dict[str, Any] | None = None,
) -> bool:
    """Round-2 landing risk aligns directly with the safe-vs-edge DEV gate.

    Reliable edge landings are the preferred targeted examples. A true swept
    non-overlap miss or a bottom terminal is accepted only as fallback evidence.
    Safe and spike landings never consume the landing-risk quota.
    """
    if "edge_landing" in events:
        return True
    reliable_miss = (
        isinstance(collision_diagnostic, dict)
        and collision_diagnostic.get("decision") == "pass_through_no_horizontal_overlap"
    )
    return bool(reliable_miss or terminal_reason == "bottom")


def validate_v35_targeted_bank(
    root: str | Path,
    manifest_path: str | Path,
    *,
    expected_policy_seed: int | None = None,
    expected_source_sha256: str | None = None,
    expected_source_timesteps: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root_path = Path(root).resolve()
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    if manifest.get("schema_version") != V35_BANK_SCHEMA:
        raise ValueError("V35_BANK_SCHEMA_MISMATCH")
    if manifest.get("generated_by_policy_lineage") != V35_BANK_LINEAGE:
        raise ValueError("V35_BANK_LINEAGE_MISMATCH")
    if manifest.get("corrected_physics_commit") != V35_CORRECTED_PHYSICS_COMMIT:
        raise ValueError("V35_BANK_CORRECTED_PHYSICS_MISMATCH")
    if manifest.get("contains_legacy_v2_or_v3_bank_entries") is not False:
        raise ValueError("V35_BANK_LEGACY_CONTAMINATION")
    if manifest.get("risk_target_counts") != V35_RISK_COUNTS:
        raise ValueError("V35_BANK_RISK_TARGET_MISMATCH")
    if int(manifest.get("success_target_count", -1)) != V35_SUCCESS_COUNT:
        raise ValueError("V35_BANK_SUCCESS_TARGET_MISMATCH")
    if manifest.get("lookback_steps") != V35_LOOKBACK:
        raise ValueError("V35_BANK_LOOKBACK_MISMATCH")
    if manifest.get("landing_risk_definition") != V35_LANDING_RISK_DEFINITION:
        raise ValueError("V35_BANK_LANDING_RISK_DEFINITION_MISMATCH")
    if manifest.get("spike_priority_health_basis") != V35_SPIKE_PRIORITY_HEALTH_BASIS:
        raise ValueError("V35_BANK_SPIKE_PRIORITY_HEALTH_BASIS_MISMATCH")
    if manifest.get("per_episode_caps") != V35_PER_EPISODE_CAPS:
        raise ValueError("V35_BANK_PER_EPISODE_CAPS_MISMATCH")
    if tuple(manifest.get("runtime_schedule", [])) != V35_RUNTIME_SCHEDULE:
        raise ValueError("V35_BANK_RUNTIME_SCHEDULE_MISMATCH")
    if manifest.get("runtime_schedule_semantics") != V35_RUNTIME_SCHEDULE_SEMANTICS:
        raise ValueError("V35_BANK_RUNTIME_SCHEDULE_SEMANTICS_MISMATCH")
    if int(manifest.get("failure_horizon_steps", -1)) != V35_FAILURE_HORIZON_STEPS:
        raise ValueError("V35_BANK_FAILURE_HORIZON_MISMATCH")
    if int(manifest.get("success_horizon_steps", -1)) != V35_SUCCESS_HORIZON_STEPS:
        raise ValueError("V35_BANK_SUCCESS_HORIZON_MISMATCH")
    if tuple(manifest.get("risk_runtime_cycle", [])) != V35_RISK_RUNTIME_CYCLE:
        raise ValueError("V35_BANK_RISK_CYCLE_MISMATCH")
    if expected_policy_seed is not None and int(manifest.get("policy_seed", -1)) != int(expected_policy_seed):
        raise ValueError("V35_BANK_POLICY_SEED_MISMATCH")
    if expected_source_sha256 is not None and manifest.get("source_model_sha256") != expected_source_sha256:
        raise ValueError("V35_BANK_SOURCE_SHA_MISMATCH")
    if expected_source_timesteps is not None and int(manifest.get("source_model_timesteps", -1)) != int(expected_source_timesteps):
        raise ValueError("V35_BANK_SOURCE_TIMESTEPS_MISMATCH")

    entries: list[dict[str, Any]] = []
    for raw in manifest.get("entries", []):
        item = dict(raw)
        path = root_path / str(item.get("snapshot_path"))
        if not path.is_file():
            raise FileNotFoundError(f"V35_BANK_SNAPSHOT_MISSING:{path}")
        actual_sha = sha256_file(path)
        if actual_sha != item.get("snapshot_sha256"):
            raise ValueError(f"V35_BANK_SNAPSHOT_SHA_MISMATCH:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "fidelity-v3-snapshot-v1":
            raise ValueError("V35_BANK_SNAPSHOT_SCHEMA_MISMATCH")
        item["snapshot"] = payload
        entries.append(item)

    counts = _entry_counts(entries)
    required = {**V35_RISK_COUNTS, "success": V35_SUCCESS_COUNT}
    if counts != required:
        raise ValueError(f"V35_BANK_COUNTS_INCOMPLETE:{counts}!={required}")
    if manifest.get("actual_counts") != counts or manifest.get("status") != "PASS":
        raise ValueError("V35_BANK_MANIFEST_STATUS_OR_COUNTS_INVALID")

    unique_counts = _unique_episode_counts(entries)
    if unique_counts != counts:
        raise ValueError(f"V35_BANK_EPISODE_DIVERSITY_INVALID:{unique_counts}!={counts}")
    if manifest.get("actual_unique_episode_counts") != unique_counts:
        raise ValueError("V35_BANK_UNIQUE_EPISODE_METADATA_INVALID")

    for item in entries:
        if item.get("source_model_sha256") != manifest.get("source_model_sha256"):
            raise ValueError("V35_BANK_ENTRY_SOURCE_SHA_MISMATCH")
        if int(item.get("policy_seed", -1)) != int(manifest.get("policy_seed", -2)):
            raise ValueError("V35_BANK_ENTRY_POLICY_SEED_MISMATCH")
        if int(item.get("source_model_timesteps", -1)) != int(manifest.get("source_model_timesteps", -2)):
            raise ValueError("V35_BANK_ENTRY_TIMESTEPS_MISMATCH")
    return manifest, entries


def collect_v35_targeted_bank(
    *,
    model: Any,
    profile_path: str | Path,
    output_dir: str | Path,
    policy_seed: int,
    source_model_sha256: str,
    source_model_timesteps: int,
    collection_seed_base: int,
    max_episodes: int = 1024,
) -> dict[str, Any]:
    if source_model_timesteps != 589_824:
        raise ValueError("V35_BANK_MUST_BE_COLLECTED_FROM_R1_CHECKPOINT")
    if max_episodes <= 0:
        raise ValueError("V35_BANK_MAX_EPISODES_INVALID")

    out = Path(output_dir).resolve()
    snapshots_dir = out / "snapshots"
    manifest_path = out / "manifest.json"
    if snapshots_dir.exists():
        for path in snapshots_dir.glob("*.json"):
            path.unlink()
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()

    entries: list[dict[str, Any]] = []
    counts = {"landing": 0, "spike": 0, "top": 0, "success": 0}
    deferred_landings: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []

    def save(
        category: str,
        snapshot: dict[str, Any],
        *,
        episode_seed: int,
        source_step: int,
        floor: int,
        health_segments: int,
        note: str,
    ) -> None:
        index = counts[category]
        snap_id = f"seed_{policy_seed}_{category}_{index:03d}"
        path = snapshots_dir / f"{snap_id}.json"
        _json_write(path, snapshot)
        entries.append(
            {
                "id": snap_id,
                "curriculum_type": "success" if category == "success" else "failure",
                "category": category,
                "snapshot_path": path.relative_to(out).as_posix(),
                "snapshot_sha256": sha256_file(path),
                "source_episode_seed": int(episode_seed),
                "source_step": int(source_step),
                "source_floor": int(floor),
                "health_segments_at_trigger": int(health_segments),
                "source_model_sha256": source_model_sha256,
                "source_model_timesteps": int(source_model_timesteps),
                "policy_seed": int(policy_seed),
                "source_note": note,
            }
        )
        counts[category] += 1

    def landing_fallback_available() -> bool:
        used = {
            int(item["source_episode_seed"])
            for item in entries
            if item.get("category") == "landing"
        }
        deferred_unique = {
            int(row["episode_seed"])
            for row in deferred_landings
            if int(row["episode_seed"]) not in used
        }
        return counts["landing"] + len(deferred_unique) >= V35_RISK_COUNTS["landing"]

    env = make_fidelity_v3_5_env(profile_path, base_seed=collection_seed_base)
    try:
        for episode_index in range(max_episodes):
            risk_ready = (
                landing_fallback_available()
                and counts["spike"] >= V35_RISK_COUNTS["spike"]
                and counts["top"] >= V35_RISK_COUNTS["top"]
            )
            if risk_ready and counts["success"] >= V35_SUCCESS_COUNT:
                break

            episode_seed = int(collection_seed_base + episode_index)
            observation, _ = env.reset(seed=episode_seed)
            history: deque[tuple[int, dict[str, Any]]] = deque(maxlen=8)
            terminated = truncated = False
            terminal_reason: str | None = None
            steps = 0
            landing_saved = False
            landing_fallback_recorded = False
            spike_saved = False
            success_saved = False

            while not (terminated or truncated):
                pre_snapshot = env.capture_portable_snapshot()
                pre_health = int(env.simulator.health_segments)
                history.append((steps, pre_snapshot))

                action, _ = model.predict(observation, deterministic=True)
                action_value = int(np.asarray(action).item())
                if action_value not in (0, 1, 2):
                    raise RuntimeError("V35_BANK_INVALID_ACTION")

                observation, _, terminated, truncated, info = env.step(action_value)
                events = {str(item) for item in info.get("events", [])}
                steps += 1
                floor = int(env.simulator.deepest_floor)
                health = int(info.get("health_segments", env.simulator.health_segments))
                collision_diagnostic = info.get("collision_diagnostic")

                if (
                    not landing_saved
                    and "edge_landing" in events
                    and counts["landing"] < V35_RISK_COUNTS["landing"]
                ):
                    source_step, snapshot = _history_snapshot(history, V35_LOOKBACK["landing"])
                    save(
                        "landing",
                        snapshot,
                        episode_seed=episode_seed,
                        source_step=source_step,
                        floor=floor,
                        health_segments=pre_health,
                        note="lookback_3_before_edge_landing",
                    )
                    landing_saved = True

                reliable_miss = (
                    isinstance(collision_diagnostic, dict)
                    and collision_diagnostic.get("decision") == "pass_through_no_horizontal_overlap"
                )
                if not landing_saved and not landing_fallback_recorded and reliable_miss:
                    source_step, snapshot = _history_snapshot(history, V35_LOOKBACK["landing"])
                    deferred_landings.append(
                        {
                            "snapshot": snapshot,
                            "episode_seed": episode_seed,
                            "source_step": source_step,
                            "floor": floor,
                            "health_segments": pre_health,
                            "note": "lookback_3_before_no_horizontal_overlap_fallback",
                        }
                    )
                    landing_fallback_recorded = True

                if (
                    "damage" in events
                    and not spike_saved
                    and counts["spike"] < V35_RISK_COUNTS["spike"]
                ):
                    source_step, snapshot = _history_snapshot(history, V35_LOOKBACK["spike"])
                    save(
                        "spike",
                        snapshot,
                        episode_seed=episode_seed,
                        source_step=source_step,
                        floor=floor,
                        health_segments=pre_health,
                        note=f"lookback_5_before_first_damage_pre_health:{pre_health}:post_health:{health}",
                    )
                    spike_saved = True

                if (
                    "safe_landing" in events
                    and floor >= V35_SUCCESS_MIN_FLOOR
                    and not success_saved
                    and counts["success"] < V35_SUCCESS_COUNT
                ):
                    source_step, snapshot = _history_snapshot(history, 0)
                    save(
                        "success",
                        snapshot,
                        episode_seed=episode_seed,
                        source_step=source_step,
                        floor=floor,
                        health_segments=health,
                        note="pre_action_state_of_floor_ge5_safe_landing_one_per_episode",
                    )
                    success_saved = True

                terminal_reason = info.get("terminal_reason")
                if steps > 10_000:
                    raise RuntimeError("V35_BANK_COLLECTION_RUNAWAY")

            floor = int(env.simulator.deepest_floor)
            health = int(env.simulator.health_segments)
            if bool(terminated) and not bool(truncated) and history:
                reason = None if terminal_reason is None else str(terminal_reason)
                if reason == "bottom" and not landing_saved and not landing_fallback_recorded:
                    source_step, snapshot = _history_snapshot(history, V35_LOOKBACK["landing"])
                    deferred_landings.append(
                        {
                            "snapshot": snapshot,
                            "episode_seed": episode_seed,
                            "source_step": source_step,
                            "floor": floor,
                            "health_segments": health,
                            "note": "lookback_3_before_bottom_terminal_fallback",
                        }
                    )
                    landing_fallback_recorded = True
                if reason == "top" and counts["top"] < V35_RISK_COUNTS["top"]:
                    source_step, snapshot = _history_snapshot(history, V35_LOOKBACK["top"])
                    save(
                        "top",
                        snapshot,
                        episode_seed=episode_seed,
                        source_step=source_step,
                        floor=floor,
                        health_segments=health,
                        note="lookback_3_before_top_terminal",
                    )

            episodes.append(
                {
                    "episode_index": episode_index,
                    "episode_seed": episode_seed,
                    "deepest_floor": floor,
                    "steps": steps,
                    "terminated": bool(terminated),
                    "truncated": bool(truncated),
                    "terminal_reason": terminal_reason,
                    "counts_after_episode": dict(counts),
                }
            )
    finally:
        env.close()

    used_landing_episodes = {
        int(item["source_episode_seed"])
        for item in entries
        if item.get("category") == "landing"
    }
    for row in deferred_landings:
        if counts["landing"] >= V35_RISK_COUNTS["landing"]:
            break
        episode_seed = int(row["episode_seed"])
        if episode_seed in used_landing_episodes:
            continue
        save(
            "landing",
            row["snapshot"],
            episode_seed=episode_seed,
            source_step=int(row["source_step"]),
            floor=int(row["floor"]),
            health_segments=int(row["health_segments"]),
            note=str(row["note"]),
        )
        used_landing_episodes.add(episode_seed)

    actual = _entry_counts(entries)
    unique_counts = _unique_episode_counts(entries)
    required = {**V35_RISK_COUNTS, "success": V35_SUCCESS_COUNT}
    complete = actual == required and unique_counts == actual
    manifest = {
        "schema_version": V35_BANK_SCHEMA,
        "generated_by_policy_lineage": V35_BANK_LINEAGE,
        "corrected_physics_commit": V35_CORRECTED_PHYSICS_COMMIT,
        "contains_legacy_v2_or_v3_bank_entries": False,
        "policy_seed": int(policy_seed),
        "source_model_sha256": source_model_sha256,
        "source_model_timesteps": int(source_model_timesteps),
        "collection_seed_base": int(collection_seed_base),
        "max_episodes": int(max_episodes),
        "risk_target_counts": dict(V35_RISK_COUNTS),
        "success_target_count": V35_SUCCESS_COUNT,
        "lookback_steps": dict(V35_LOOKBACK),
        "landing_risk_definition": V35_LANDING_RISK_DEFINITION,
        "spike_priority_health_basis": V35_SPIKE_PRIORITY_HEALTH_BASIS,
        "per_episode_caps": dict(V35_PER_EPISODE_CAPS),
        "success_min_floor": V35_SUCCESS_MIN_FLOOR,
        "success_requires_safe_landing": True,
        "runtime_schedule": list(V35_RUNTIME_SCHEDULE),
        "runtime_schedule_semantics": V35_RUNTIME_SCHEDULE_SEMANTICS,
        "failure_horizon_steps": V35_FAILURE_HORIZON_STEPS,
        "success_horizon_steps": V35_SUCCESS_HORIZON_STEPS,
        "risk_runtime_cycle": list(V35_RISK_RUNTIME_CYCLE),
        "actual_counts": actual,
        "actual_unique_episode_counts": unique_counts,
        "entries": entries,
        "episodes": episodes,
        "status": "PASS" if complete else "INSUFFICIENT_TARGETED_CURRICULUM",
    }
    _json_write(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)

    if not complete:
        raise RuntimeError(
            f"V35_TARGETED_BANK_INCOMPLETE:counts={actual}:unique={unique_counts}"
        )
    validate_v35_targeted_bank(
        out,
        manifest_path,
        expected_policy_seed=policy_seed,
        expected_source_sha256=source_model_sha256,
        expected_source_timesteps=source_model_timesteps,
    )
    return manifest


class V35TargetedCurriculumEnv(gym.Env[np.ndarray, int]):
    """A fixed targeted vector lane used only in V3.5 Round 3 R2.

    Round 2 scheduled targeted resets by episode count, so the few hazard-near
    transitions were diluted by long ordinary continuations. Round 3 binds one
    vector lane to failure and one to success and truncates targeted bursts after
    a short horizon. Stable-Baselines3 bootstraps TimeLimit truncations, so these
    curriculum boundaries are not treated as deaths.
    """

    def __init__(
        self,
        *,
        profile_path: str | Path,
        bank_root: str | Path,
        bank_manifest_path: str | Path,
        base_seed: int,
        expected_policy_seed: int,
        expected_source_sha256: str,
        fixed_mode: str,
        expected_source_timesteps: int = 589_824,
    ) -> None:
        super().__init__()
        if fixed_mode not in {"failure", "success"}:
            raise ValueError(f"V35_TARGETED_FIXED_MODE_INVALID:{fixed_mode}")
        self.profile_path = Path(profile_path)
        self.base_seed = int(base_seed)
        self.fixed_mode = str(fixed_mode)
        self.horizon_steps = (
            V35_FAILURE_HORIZON_STEPS
            if self.fixed_mode == "failure"
            else V35_SUCCESS_HORIZON_STEPS
        )
        self.underlying_env: FidelityV35Env = make_fidelity_v3_5_env(
            self.profile_path,
            base_seed=self.base_seed,
        )
        self.bank_manifest, entries = validate_v35_targeted_bank(
            bank_root,
            bank_manifest_path,
            expected_policy_seed=expected_policy_seed,
            expected_source_sha256=expected_source_sha256,
            expected_source_timesteps=expected_source_timesteps,
        )
        self.by_category = {
            category: [item for item in entries if item["category"] == category]
            for category in ("landing", "spike", "top", "success")
        }
        self.action_space = self.underlying_env.action_space
        self.observation_space = self.underlying_env.observation_space
        self._risk_index = 0
        self._category_indices = {key: 0 for key in self.by_category}
        self._steps_since_reset = 0

    @property
    def simulator(self) -> Any:
        return self.underlying_env.simulator

    @property
    def config(self) -> Any:
        return self.underlying_env.config

    @property
    def cadence_hz(self) -> int:
        return self.underlying_env.cadence_hz

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        del options
        if seed is not None:
            self.base_seed = int(seed)
            self._risk_index = 0
            self._category_indices = {key: 0 for key in self.by_category}

        if self.fixed_mode == "success":
            category = "success"
        else:
            category = V35_RISK_RUNTIME_CYCLE[
                self._risk_index % len(V35_RISK_RUNTIME_CYCLE)
            ]
            self._risk_index += 1
        pool = self.by_category[category]
        index = self._category_indices[category]
        self._category_indices[category] += 1
        entry = pool[index % len(pool)]
        observation = self.underlying_env.restore_portable_snapshot(entry["snapshot"])
        info = self.underlying_env._info()
        info["curriculum_snapshot_id"] = entry["id"]
        info["curriculum_category"] = category
        info["reset_mode"] = self.fixed_mode
        info["curriculum_lane_mode"] = self.fixed_mode
        info["curriculum_horizon_steps"] = int(self.horizon_steps)
        info["v3_5_targeted_curriculum"] = True
        self._steps_since_reset = 0

        if observation.shape != (268,) or not np.isfinite(observation).all():
            raise RuntimeError("V35_TARGETED_RESET_OBSERVATION_INVALID")
        return observation, info

    def step(
        self,
        action: int,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        observation, reward, terminated, truncated, info = self.underlying_env.step(action)
        self._steps_since_reset += 1
        horizon_hit = (
            not terminated
            and not truncated
            and self._steps_since_reset >= self.horizon_steps
        )
        if horizon_hit:
            truncated = True
            info = dict(info)
            info["curriculum_horizon_truncated"] = True
            info["curriculum_horizon_steps"] = int(self.horizon_steps)
            info["curriculum_lane_mode"] = self.fixed_mode
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        self.underlying_env.close()


__all__ = [
    "V35_BANK_LINEAGE",
    "V35_BANK_SCHEMA",
    "V35_FAILURE_HORIZON_STEPS",
    "V35_LANDING_RISK_DEFINITION",
    "V35_LOOKBACK",
    "V35_PER_EPISODE_CAPS",
    "V35_RISK_COUNTS",
    "V35_RISK_RUNTIME_CYCLE",
    "V35_RUNTIME_SCHEDULE",
    "V35_RUNTIME_SCHEDULE_SEMANTICS",
    "V35_SUCCESS_HORIZON_STEPS",
    "V35_SPIKE_PRIORITY_HEALTH_BASIS",
    "V35_SUCCESS_COUNT",
    "V35TargetedCurriculumEnv",
    "collect_v35_targeted_bank",
    "is_v35_landing_risk_event",
    "sha256_file",
    "validate_v35_targeted_bank",
]
