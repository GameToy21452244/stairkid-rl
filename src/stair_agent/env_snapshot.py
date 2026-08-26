"""Environment Snapshot capture and restore utilities for FidelityV2Env.

Preserves full environment state including simulator physics, temporal observation frame stack,
previous-action temporal stack, last_observation, step_count, diagnostics, reward calculator,
and observation RNG state.

Provides portable, versioned, deterministic serialization/deserialization without pickle dependency.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from stair_agent.simulator.physics import PlatformSnapshot, SimulatorSnapshot

PORTABLE_SNAPSHOT_SCHEMA_VERSION = "v1"


@dataclass
class EnvSnapshot:
    simulator: Any
    frames: tuple[np.ndarray, ...]
    actions: tuple[np.ndarray, ...]
    last_observation: Any
    step_count: int
    diagnostics: dict[str, object]
    reward_state: dict[str, object]
    observation_rng_state: dict[str, object]


def capture_env(env: Any) -> EnvSnapshot:
    """Captures a complete, replay-safe snapshot of a FidelityV2Env instance."""
    return EnvSnapshot(
        simulator=env.simulator.capture_snapshot(),
        frames=tuple(frame.copy() for frame in env.temporal_stack._frames),
        actions=tuple(action.copy() for action in env.temporal_stack._actions),
        last_observation=copy.deepcopy(env.last_observation),
        step_count=int(env._step_count),
        diagnostics=copy.deepcopy(env._diagnostics),
        reward_state=copy.deepcopy(env.reward_calculator.__dict__),
        observation_rng_state=copy.deepcopy(env._observation_rng.bit_generator.state),
    )


def restore_env(env: Any, snapshot: EnvSnapshot) -> np.ndarray:
    """Restores a FidelityV2Env instance from an EnvSnapshot and returns the flattened 268-D observation vector."""
    env.simulator.restore_snapshot(snapshot.simulator)
    env.temporal_stack._frames = deque(
        (value.copy() for value in snapshot.frames),
        maxlen=env.temporal_stack.history_frames,
    )
    env.temporal_stack._actions = deque(
        (value.copy() for value in snapshot.actions),
        maxlen=env.temporal_stack.history_frames,
    )
    env.last_observation = copy.deepcopy(snapshot.last_observation)
    env._step_count = snapshot.step_count
    env.reward_calculator.__dict__.clear()
    env.reward_calculator.__dict__.update(copy.deepcopy(snapshot.reward_state))
    if isinstance(getattr(env.reward_calculator, "config", None), dict):
        from stair_agent.simulator.state import ShaftEnvConfig
        try:
            env.reward_calculator.config = ShaftEnvConfig(**env.reward_calculator.config)
        except Exception:
            pass
    env._observation_rng.bit_generator.state = copy.deepcopy(
        snapshot.observation_rng_state
    )
    return env.temporal_stack._flatten().copy()



from dataclasses import is_dataclass, asdict
from stair_agent.observation import GameObservation


def _sanitize_for_json(obj: Any) -> Any:
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _sanitize_for_json(obj.to_dict())
    if is_dataclass(obj) and not isinstance(obj, type):
        return _sanitize_for_json(asdict(obj))
    if hasattr(obj, "__dict__"):
        return _sanitize_for_json(obj.__dict__)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, (tuple, list)):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    return obj



def env_snapshot_to_portable_dict(snapshot: EnvSnapshot) -> dict[str, Any]:
    """Converts an EnvSnapshot dataclass into a portable, JSON-serializable dictionary."""
    sim = snapshot.simulator
    sim_dict = {
        "player_position": [float(sim.player_position[0]), float(sim.player_position[1])],
        "player_velocity": [float(sim.player_velocity[0]), float(sim.player_velocity[1])],
        "player_angle": float(sim.player_angle),
        "player_angular_velocity": float(sim.player_angular_velocity),
        "player_force": [float(sim.player_force[0]), float(sim.player_force[1])],
        "player_torque": float(sim.player_torque),
        "platforms": [
            {
                "floor_index": int(p.floor_index),
                "center_x": float(p.center_x),
                "center_y": float(p.center_y),
                "kind": str(p.kind),
            }
            for p in sim.platforms
        ],
        "deepest_floor": int(sim.deepest_floor),
        "last_landed_floor": int(sim.last_landed_floor) if sim.last_landed_floor is not None else None,
        "supported_floor": int(sim.supported_floor) if sim.supported_floor is not None else None,
        "physics_substep_accumulator": float(sim.physics_substep_accumulator),
        "health_segments": int(sim.health_segments),
        "last_health_delta": int(sim.last_health_delta),
        "last_conveyor_velocity_delta_x": float(sim.last_conveyor_velocity_delta_x),
        "last_spring_velocity_delta_y": float(sim.last_spring_velocity_delta_y),
        "elapsed_seconds": float(sim.elapsed_seconds),
        "rng_state": _sanitize_for_json(sim.rng_state),
        "flipping_runtime_states": [
            [int(st[0]), str(st[1]), float(st[2])] for st in sim.flipping_runtime_states
        ],
    }

    return {
        "schema_version": PORTABLE_SNAPSHOT_SCHEMA_VERSION,
        "simulator": sim_dict,
        "frames": [f.tolist() for f in snapshot.frames],
        "actions": [a.tolist() for a in snapshot.actions],
        "last_observation": _sanitize_for_json(snapshot.last_observation),
        "step_count": int(snapshot.step_count),
        "diagnostics": _sanitize_for_json(snapshot.diagnostics),
        "reward_state": _sanitize_for_json(snapshot.reward_state),
        "observation_rng_state": _sanitize_for_json(snapshot.observation_rng_state),
    }


def portable_dict_to_env_snapshot(data: dict[str, Any]) -> EnvSnapshot:
    """Reconstructs an EnvSnapshot dataclass from a portable dictionary."""
    schema = data.get("schema_version")
    if schema != PORTABLE_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported portable snapshot schema version: '{schema}' (expected '{PORTABLE_SNAPSHOT_SCHEMA_VERSION}')."
        )

    sim_d = data["simulator"]
    platforms = tuple(
        PlatformSnapshot(
            floor_index=int(p["floor_index"]),
            center_x=float(p["center_x"]),
            center_y=float(p["center_y"]),
            kind=str(p["kind"]),
        )
        for p in sim_d["platforms"]
    )

    # Reconstruct uint32 arrays in rng_state if needed
    sim_rng_state = copy.deepcopy(sim_d["rng_state"])
    if isinstance(sim_rng_state, dict) and "state" in sim_rng_state:
        st = sim_rng_state["state"]
        if isinstance(st, dict) and "key" in st:
            st["key"] = np.array(st["key"], dtype=np.uint32)

    sim_snapshot = SimulatorSnapshot(
        player_position=(float(sim_d["player_position"][0]), float(sim_d["player_position"][1])),
        player_velocity=(float(sim_d["player_velocity"][0]), float(sim_d["player_velocity"][1])),
        player_angle=float(sim_d["player_angle"]),
        player_angular_velocity=float(sim_d["player_angular_velocity"]),
        player_force=(float(sim_d["player_force"][0]), float(sim_d["player_force"][1])),
        player_torque=float(sim_d["player_torque"]),
        platforms=platforms,
        platform_objects=tuple(),  # Handled cleanly by restore_snapshot in physics.py
        deepest_floor=int(sim_d["deepest_floor"]),
        last_landed_floor=int(sim_d["last_landed_floor"]) if sim_d["last_landed_floor"] is not None else None,
        supported_floor=int(sim_d["supported_floor"]) if sim_d["supported_floor"] is not None else None,
        physics_substep_accumulator=float(sim_d["physics_substep_accumulator"]),
        health_segments=int(sim_d["health_segments"]),
        last_health_delta=int(sim_d["last_health_delta"]),
        last_conveyor_velocity_delta_x=float(sim_d["last_conveyor_velocity_delta_x"]),
        last_spring_velocity_delta_y=float(sim_d["last_spring_velocity_delta_y"]),
        elapsed_seconds=float(sim_d["elapsed_seconds"]),
        rng_state=sim_rng_state,
        flipping_runtime_states=tuple(
            (int(st[0]), str(st[1]), float(st[2])) for st in sim_d["flipping_runtime_states"]
        ),
    )

    frames = tuple(np.array(f, dtype=np.float32) for f in data["frames"])
    actions = tuple(np.array(a, dtype=np.float32) for a in data["actions"])

    obs_rng_state = copy.deepcopy(data["observation_rng_state"])
    if isinstance(obs_rng_state, dict) and "state" in obs_rng_state:
        st = obs_rng_state["state"]
        if isinstance(st, dict) and "key" in st:
            st["key"] = np.array(st["key"], dtype=np.uint32)

    last_obs = copy.deepcopy(data["last_observation"])
    if isinstance(last_obs, dict) and "timestamp" in last_obs and "phase" in last_obs:
        try:
            last_obs = GameObservation(**last_obs)
        except Exception:
            pass

    return EnvSnapshot(
        simulator=sim_snapshot,
        frames=frames,
        actions=actions,
        last_observation=last_obs,
        step_count=int(data["step_count"]),
        diagnostics=copy.deepcopy(data["diagnostics"]),
        reward_state=copy.deepcopy(data["reward_state"]),
        observation_rng_state=obs_rng_state,
    )



def compute_env_snapshot_semantic_hash(snapshot: EnvSnapshot) -> str:
    """Computes a deterministic SHA256 semantic hash of an EnvSnapshot."""
    pdict = env_snapshot_to_portable_dict(snapshot)
    payload = json.dumps(pdict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def serialize_env_snapshot(snapshot: EnvSnapshot, path: Path) -> str:
    """Serializes an EnvSnapshot to disk as a portable JSON file with LF line endings and returns its file SHA256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdict = env_snapshot_to_portable_dict(snapshot)
    payload_bytes = (json.dumps(pdict, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload_bytes)
    return hashlib.sha256(payload_bytes).hexdigest()



def deserialize_env_snapshot(path: Path) -> EnvSnapshot:
    """Deserializes a portable JSON snapshot file back into an EnvSnapshot dataclass."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Portable snapshot file not found: {path}")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return portable_dict_to_env_snapshot(data)
