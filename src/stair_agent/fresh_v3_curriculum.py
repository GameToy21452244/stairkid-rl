from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from .envs.fidelity_v3 import FidelityV3Env
from .envs.fidelity_v3_fresh import make_fidelity_v3_fresh_env

FRESH_V3_BANK_SCHEMA = "fresh-v3-self-curriculum-v1"
SUCCESS_SNAPSHOTS_MAX_PER_EPISODE = 3
FRESH_FAILURE_TERMINAL_REASONS = frozenset({"bottom", "top", "health_depleted"})
RUNTIME_BANK_CONTRACTS = {
    "stage_a_to_b": {
        "source_timesteps": 196_608,
        "stage_offset": 0,
        "schedule_cycle": ("ordinary", "ordinary", "ordinary", "ordinary", "ordinary", "ordinary", "failure", "success"),
    },
    "stage_b_to_c": {
        "source_timesteps": 393_216,
        "stage_offset": 5_000_000,
        "schedule_cycle": ("ordinary", "ordinary", "failure", "success"),
    },
}


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


def is_fresh_failure_terminal(*, terminated: bool, truncated: bool, terminal_reason: str | None) -> bool:
    """Only genuine game-over deaths are eligible for Fresh failure curriculum."""
    return bool(
        terminated
        and not truncated
        and terminal_reason is not None
        and str(terminal_reason) in FRESH_FAILURE_TERMINAL_REASONS
    )


def validate_fresh_bank_runtime_binding(root: str | Path, manifest: dict[str, Any]) -> str:
    """Bind formal Stage B/C banks to the exact checkpoint and collection contract."""
    root_path = Path(root).resolve()
    stage_name = root_path.name
    contract = RUNTIME_BANK_CONTRACTS.get(stage_name)
    if contract is None:
        return "NOT_FORMAL_RUNTIME_BANK_PATH"
    try:
        seed = int(manifest["policy_seed"])
    except Exception as exc:
        raise ValueError("FRESH_V3_BANK_RUNTIME_POLICY_SEED_INVALID") from exc
    if root_path.parent.name != f"seed_{seed}" or root_path.parent.parent.name != "banks":
        raise ValueError("FRESH_V3_BANK_RUNTIME_PATH_SEED_MISMATCH")
    source_timesteps = int(contract["source_timesteps"])
    run_dir = root_path.parents[2]
    source_model = run_dir / f"seed_{seed}" / "checkpoints" / f"fresh_v3_{source_timesteps:06d}.zip"
    if not source_model.is_file():
        raise FileNotFoundError(f"FRESH_V3_BANK_SOURCE_CHECKPOINT_MISSING:{source_model}")
    if int(manifest.get("source_model_timesteps", -1)) != source_timesteps:
        raise ValueError("FRESH_V3_BANK_SOURCE_TIMESTEPS_MISMATCH")
    if manifest.get("source_model_sha256") != sha256_file(source_model):
        raise ValueError("FRESH_V3_BANK_SOURCE_CHECKPOINT_SHA_MISMATCH")
    expected_collection_seed = 20_000_000 + seed * 100_000 + int(contract["stage_offset"])
    expected = {
        "collection_seed_base": expected_collection_seed,
        "target_per_class": 48,
        "max_episodes": 256,
        "failure_lookback_steps": 3,
        "success_min_floor": 5,
        "success_snapshots_max_per_episode": SUCCESS_SNAPSHOTS_MAX_PER_EPISODE,
        "stage_label": f"seed_{seed}_{stage_name}",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"FRESH_V3_BANK_RUNTIME_CONTRACT_MISMATCH:{key}:{manifest.get(key)}!={value}")
    if tuple(map(str, manifest.get("schedule_cycle", []))) != tuple(contract["schedule_cycle"]):
        raise ValueError("FRESH_V3_BANK_RUNTIME_SCHEDULE_MISMATCH")
    return "PASS"


def load_fresh_curriculum_bank(root: str | Path, manifest_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root_path = Path(root).resolve()
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != FRESH_V3_BANK_SCHEMA:
        raise ValueError("FRESH_V3_BANK_SCHEMA_MISMATCH")
    if manifest.get("generated_by_policy_lineage") != "fresh-random-init-v1":
        raise ValueError("FRESH_V3_BANK_POLICY_LINEAGE_MISMATCH")
    if manifest.get("contains_legacy_v2_or_v3_bank_entries") is not False:
        raise ValueError("FRESH_V3_BANK_LEGACY_CONTAMINATION_FLAG")
    if int(manifest.get("success_snapshots_max_per_episode", -1)) != SUCCESS_SNAPSHOTS_MAX_PER_EPISODE:
        raise ValueError("FRESH_V3_BANK_SUCCESS_DIVERSITY_CONTRACT_MISMATCH")
    if set(map(str, manifest.get("failure_terminal_reasons", []))) != set(FRESH_FAILURE_TERMINAL_REASONS):
        raise ValueError("FRESH_V3_BANK_FAILURE_REASON_CONTRACT_MISMATCH")
    validate_fresh_bank_runtime_binding(root_path, manifest)
    entries = []
    for raw in manifest.get("entries", []):
        item = dict(raw)
        path = Path(item["snapshot_path"])
        if not path.is_absolute():
            path = root_path / path
        if not path.is_file():
            raise FileNotFoundError(f"FRESH_V3_BANK_SNAPSHOT_MISSING:{path}")
        if sha256_file(path) != item.get("snapshot_sha256"):
            raise ValueError(f"FRESH_V3_BANK_SNAPSHOT_SHA_MISMATCH:{path.name}")
        item["snapshot"] = json.loads(path.read_text(encoding="utf-8"))
        entries.append(item)
    failure = [item for item in entries if item.get("curriculum_type") == "failure"]
    success = [item for item in entries if item.get("curriculum_type") == "success"]
    target = int(manifest.get("target_per_class", 0))
    if target <= 0 or len(failure) < target or len(success) < target:
        raise ValueError(f"FRESH_V3_BANK_INCOMPLETE:failure={len(failure)}:success={len(success)}:target={target}")
    return manifest, entries


def collect_self_curriculum_bank(
    *,
    model: Any,
    profile_path: str | Path,
    output_dir: str | Path,
    policy_seed: int,
    source_model_sha256: str,
    source_model_timesteps: int,
    collection_seed_base: int,
    target_per_class: int,
    max_episodes: int,
    failure_lookback_steps: int,
    success_min_floor: int,
    schedule_cycle: tuple[str, ...],
    stage_label: str,
    success_snapshots_max_per_episode: int = SUCCESS_SNAPSHOTS_MAX_PER_EPISODE,
) -> dict[str, Any]:
    if target_per_class <= 0 or max_episodes <= 0 or failure_lookback_steps <= 0:
        raise ValueError("FRESH_V3_BANK_COLLECTION_ARGUMENTS")
    if success_snapshots_max_per_episode != SUCCESS_SNAPSHOTS_MAX_PER_EPISODE:
        raise ValueError("FRESH_V3_BANK_SUCCESS_DIVERSITY_CONTRACT_MISMATCH")
    if not schedule_cycle or any(mode not in {"ordinary", "failure", "success"} for mode in schedule_cycle):
        raise ValueError("FRESH_V3_BANK_SCHEDULE_INVALID")
    out = Path(output_dir).resolve()
    snapshots_dir = out / "snapshots"
    manifest_path = out / "manifest.json"
    # collect_self_curriculum_bank() is only entered when the caller has decided
    # to build/rebuild this bank. Remove partial or stale bank-local artifacts so
    # they cannot leak into the new manifest or handoff.
    if snapshots_dir.is_dir():
        for stale in snapshots_dir.glob("*.json"):
            stale.unlink()
    if manifest_path.is_file():
        manifest_path.unlink()
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    failure_count = 0
    success_count = 0
    episode_rows: list[dict[str, Any]] = []

    def save_snapshot(kind: str, payload: dict[str, Any], *, episode_seed: int, floor: int, source_step: int, note: str) -> None:
        nonlocal failure_count, success_count
        index = failure_count if kind == "failure" else success_count
        snap_id = f"{stage_label}_{kind}_{index:03d}"
        path = snapshots_dir / f"{snap_id}.json"
        _json_write(path, payload)
        entries.append({
            "id": snap_id,
            "curriculum_type": kind,
            "snapshot_path": path.relative_to(out).as_posix(),
            "snapshot_sha256": sha256_file(path),
            "source_episode_seed": int(episode_seed),
            "source_floor": int(floor),
            "source_step": int(source_step),
            "source_note": note,
        })
        if kind == "failure":
            failure_count += 1
        else:
            success_count += 1

    env = make_fidelity_v3_fresh_env(profile_path, base_seed=collection_seed_base)
    for episode_index in range(max_episodes):
        if failure_count >= target_per_class and success_count >= target_per_class:
            break
        episode_seed = int(collection_seed_base + episode_index)
        observation, _ = env.reset(seed=episode_seed)
        history: deque[tuple[int, dict[str, Any]]] = deque(maxlen=max(2, failure_lookback_steps + 2))
        terminated = truncated = False
        steps = 0
        success_saved_this_episode = 0
        terminal_reason = None
        while not (terminated or truncated):
            pre_snapshot = env.capture_portable_snapshot()
            history.append((steps, pre_snapshot))
            action, _ = model.predict(observation, deterministic=True)
            action_value = int(np.asarray(action).item())
            if action_value not in (0, 1, 2):
                raise RuntimeError("FRESH_V3_BANK_INVALID_ACTION")
            observation, _, terminated, truncated, info = env.step(action_value)
            steps += 1
            events = {str(item) for item in info.get("events", [])}
            floor = int(env.simulator.deepest_floor)
            if (
                success_saved_this_episode < success_snapshots_max_per_episode
                and success_count < target_per_class
                and floor >= success_min_floor
                and "floor_descended" in events
            ):
                save_snapshot(
                    "success",
                    pre_snapshot,
                    episode_seed=episode_seed,
                    floor=floor,
                    source_step=steps - 1,
                    note="pre_action_state_of_successful_floor_descended_transition",
                )
                success_saved_this_episode += 1
            terminal_reason = info.get("terminal_reason")
            if steps > 10_000:
                raise RuntimeError("FRESH_V3_BANK_COLLECTION_RUNAWAY")
        floor = int(env.simulator.deepest_floor)
        failure_eligible = is_fresh_failure_terminal(
            terminated=bool(terminated),
            truncated=bool(truncated),
            terminal_reason=None if terminal_reason is None else str(terminal_reason),
        )
        failure_snapshot_saved = False
        if failure_count < target_per_class and history and failure_eligible:
            desired = max(0, len(history) - 1 - failure_lookback_steps)
            source_step, failure_snapshot = list(history)[desired]
            save_snapshot(
                "failure",
                failure_snapshot,
                episode_seed=episode_seed,
                floor=floor,
                source_step=source_step,
                note=f"lookback_{failure_lookback_steps}_steps_before_terminal:{terminal_reason}",
            )
            failure_snapshot_saved = True
        episode_rows.append({
            "episode_index": episode_index,
            "episode_seed": episode_seed,
            "deepest_floor": floor,
            "steps": steps,
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "terminal_reason": terminal_reason,
            "failure_eligible": failure_eligible,
            "failure_snapshot_saved": failure_snapshot_saved,
            "success_snapshots_saved": success_saved_this_episode,
        })
    env.close()

    manifest = {
        "schema_version": FRESH_V3_BANK_SCHEMA,
        "generated_by_policy_lineage": "fresh-random-init-v1",
        "contains_legacy_v2_or_v3_bank_entries": False,
        "stage_label": stage_label,
        "policy_seed": int(policy_seed),
        "source_model_sha256": source_model_sha256,
        "source_model_timesteps": int(source_model_timesteps),
        "collection_seed_base": int(collection_seed_base),
        "target_per_class": int(target_per_class),
        "max_episodes": int(max_episodes),
        "failure_lookback_steps": int(failure_lookback_steps),
        "failure_terminal_reasons": sorted(FRESH_FAILURE_TERMINAL_REASONS),
        "success_min_floor": int(success_min_floor),
        "success_snapshots_max_per_episode": int(success_snapshots_max_per_episode),
        "schedule_cycle": list(schedule_cycle),
        "failure_count": failure_count,
        "success_count": success_count,
        "entries": entries,
        "episodes": episode_rows,
    }
    if failure_count < target_per_class or success_count < target_per_class:
        manifest["status"] = "INSUFFICIENT_SELF_CURRICULUM"
    else:
        manifest["status"] = "PASS"
    _json_write(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    return manifest


class FreshV3SelfCurriculumEnv(gym.Env[np.ndarray, int]):
    def __init__(
        self,
        *,
        profile_path: str | Path,
        bank_manifest_path: str | Path,
        bank_root: str | Path,
        base_seed: int,
    ) -> None:
        super().__init__()
        self.profile_path = Path(profile_path)
        self.base_seed = int(base_seed)
        self.underlying_env: FidelityV3Env = make_fidelity_v3_fresh_env(self.profile_path, base_seed=self.base_seed)
        self.bank_manifest, entries = load_fresh_curriculum_bank(bank_root, bank_manifest_path)
        self.failure_entries = [item for item in entries if item["curriculum_type"] == "failure"]
        self.success_entries = [item for item in entries if item["curriculum_type"] == "success"]
        self.schedule_cycle = tuple(map(str, self.bank_manifest["schedule_cycle"]))
        self.action_space = self.underlying_env.action_space
        self.observation_space = self.underlying_env.observation_space
        self._reset_index = 0
        self._failure_index = 0
        self._success_index = 0

    @property
    def simulator(self) -> Any:
        return self.underlying_env.simulator

    @property
    def config(self) -> Any:
        return self.underlying_env.config

    @property
    def cadence_hz(self) -> int:
        return self.underlying_env.cadence_hz

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        del options
        if seed is not None:
            self.base_seed = int(seed)
            self._reset_index = 0
            self._failure_index = 0
            self._success_index = 0
        mode = self.schedule_cycle[self._reset_index % len(self.schedule_cycle)]
        self._reset_index += 1
        if mode == "ordinary":
            observation, info = self.underlying_env.reset(seed=self.base_seed + self._reset_index)
        else:
            pool = self.failure_entries if mode == "failure" else self.success_entries
            index = self._failure_index if mode == "failure" else self._success_index
            entry = pool[index % len(pool)]
            if mode == "failure":
                self._failure_index += 1
            else:
                self._success_index += 1
            observation = self.underlying_env.restore_portable_snapshot(entry["snapshot"])
            info = self.underlying_env._info()
            info["curriculum_snapshot_id"] = entry["id"]
        info["reset_mode"] = mode
        info["fresh_self_curriculum"] = True
        return observation, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        return self.underlying_env.step(action)

    def close(self) -> None:
        self.underlying_env.close()


__all__ = [
    "FRESH_V3_BANK_SCHEMA",
    "FRESH_FAILURE_TERMINAL_REASONS",
    "RUNTIME_BANK_CONTRACTS",
    "SUCCESS_SNAPSHOTS_MAX_PER_EPISODE",
    "FreshV3SelfCurriculumEnv",
    "collect_self_curriculum_bank",
    "is_fresh_failure_terminal",
    "load_fresh_curriculum_bank",
    "validate_fresh_bank_runtime_binding",
    "sha256_file",
]