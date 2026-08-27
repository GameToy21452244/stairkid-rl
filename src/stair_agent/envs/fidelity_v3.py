"""Training/simulator-only Real-Anchored Fidelity V3 implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pymunk
from ..env_snapshot import capture_env, env_snapshot_to_portable_dict, portable_dict_to_env_snapshot, restore_env
from ..observation import GameObservation
from ..simulator.fidelity_v3_generator import V3LayoutProfile, generate_v3_platforms
from ..simulator.physics import ShaftSimulator
from ..simulator.player import SimulatorPlayer
from .physics_profile import PhysicsProfile, RANDOMIZED_FIELDS
from .reward import SimulatorRewardCalculator
from .shaft_env import ShaftEnv


FIDELITY_V3_VERSION = "ns-shaft-sim-real-anchored-v3-v0.1"
@dataclass(frozen=True)
class ObservationEmulatorProfile:
    player_center_quantum_px: float
    player_position_noise_uniform_px: float
    player_dropout_start_probability: float
    player_dropout_continue_probability: float
    player_dropout_max_frames: int
    platform_box_quantum_px: float
    platform_position_noise_uniform_px: float
    platform_track_dropout_start_probability: float
    platform_track_dropout_continue_probability: float
    platform_track_dropout_max_frames: int
    visible_count_initial_pmf: dict[int, float]
    visible_count_transition: dict[int, dict[int, float]]
    no_match_scroll_value_px_s: float

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ObservationEmulatorProfile":
        values = dict(raw)
        values["visible_count_initial_pmf"] = {int(k): float(v) for k, v in raw["visible_count_initial_pmf"].items()}
        values["visible_count_transition"] = {
            int(k): {int(j): float(p) for j, p in row.items()}
            for k, row in raw["visible_count_transition"].items()
        }
        profile = cls(**values)
        profile.validate()
        return profile

    def validate(self) -> None:
        for probability in (
            self.player_dropout_start_probability,
            self.player_dropout_continue_probability,
            self.platform_track_dropout_start_probability,
            self.platform_track_dropout_continue_probability,
        ):
            if not 0.0 <= probability <= 1.0:
                raise ValueError("V3_OBSERVATION_PROBABILITY")
        if abs(sum(self.visible_count_initial_pmf.values()) - 1.0) > 2e-6:
            raise ValueError("V3_VISIBLE_INITIAL_PMF")
        for row in self.visible_count_transition.values():
            if abs(sum(row.values()) - 1.0) > 2e-6:
                raise ValueError("V3_VISIBLE_TRANSITION_PMF")


@dataclass(frozen=True)
class FidelityV3Profile:
    path: Path
    parent: PhysicsProfile
    layout: V3LayoutProfile
    layout_raw: dict[str, Any]
    observation: ObservationEmulatorProfile
    cadence_probabilities: dict[int, float]
    curriculum_cycle: tuple[str, ...]
    preflight_gates: dict[str, float]
    provenance: dict[str, Any]


def load_fidelity_v3_profile(path: str | Path) -> FidelityV3Profile:
    del path
    raise ValueError("LEGACY_FIDELITY_V3_PROFILE_RETIRED_USE_FRESH_PROFILE")


def derive_v3_seeds(master_seed: int) -> dict[str, int]:
    names = ("layout_seed", "physics_dr_seed", "observation_seed", "cadence_seed", "special_seed")
    children = np.random.SeedSequence(int(master_seed)).spawn(len(names))
    return {name: int(child.generate_state(1, dtype=np.uint32)[0]) for name, child in zip(names, children, strict=True)}


def _categorical(rng: np.random.Generator, probabilities: dict[int, float]) -> int:
    keys = sorted(probabilities)
    values = np.asarray([probabilities[key] for key in keys], dtype=float)
    values /= values.sum()
    return int(rng.choice(keys, p=values))


class FidelityV3Simulator(ShaftSimulator):
    """Shaft physics with an isolated V3 platform factory."""

    def __init__(self, config: Any, rng: np.random.Generator, layout: V3LayoutProfile) -> None:
        self.config = config
        self.rng = rng
        self.space = pymunk.Space()
        self.space.gravity = (0.0, config.gravity)
        self.platforms, self.layout_diagnostics = generate_v3_platforms(config, rng, layout)
        first = self.platforms[0]
        self.player = SimulatorPlayer(
            width=config.player_width, height=config.player_height,
            position=(first.center_x, first.top + config.player_height / 2),
        )
        self.space.add(self.player.body, self.player.shape)
        for platform in self.platforms:
            self.space.add(platform.body, platform.shape)
        self.deepest_floor = 0
        self.last_landed_floor = None
        self.supported_floor = first.floor_index if config.enable_support_ownership else None
        self._physics_substep_accumulator = 0.0
        self.health_segments = config.initial_health_segments
        self.last_health_delta = 0
        self.last_conveyor_velocity_delta_x = 0.0
        self.last_spring_velocity_delta_y = 0.0
        self.elapsed_seconds = 0.0
        self.last_collision_diagnostic = None
        self.flipping_states = {
            platform.floor_index: {"state": "READY", "elapsed": 0.0}
            for platform in self.platforms if platform.kind == "flipping"
        }


class RealStyleObservationEmulator:
    """Seeded measurement process; privileged physics never reaches the encoder."""

    def __init__(self, profile: ObservationEmulatorProfile, rng: np.random.Generator) -> None:
        self.profile = profile
        self.rng = rng
        self.reset_state()

    def reset_state(self) -> None:
        # Keep the last *raw* measurement separate from the currently emitted
        # tracked position.  This mirrors PlayerTracker: extrapolated dropout
        # frames never replace the finite-difference anchor.
        self.last_raw_player: dict[str, float] | None = None
        self.last_raw_timestamp: float | None = None
        self.last_raw_velocity = {"x": 0.0, "y": 0.0}
        self.last_raw_motion = "unknown"
        self.emitted_player: dict[str, Any] | None = None
        self.previous_platforms: dict[int, dict[str, Any]] = {}
        self.player_dropout_streak = 0
        self.platform_dropout_streaks: dict[int, int] = {}
        self.platform_priorities: dict[int, float] = {}
        self.visible_target: int | None = None
        self.last_diagnostics: dict[str, Any] = {}

    def state_dict(self) -> dict[str, Any]:
        return {
            "rng_state": deepcopy(self.rng.bit_generator.state),
            "last_raw_player": deepcopy(self.last_raw_player),
            "last_raw_timestamp": self.last_raw_timestamp,
            "last_raw_velocity": dict(self.last_raw_velocity),
            "last_raw_motion": self.last_raw_motion,
            "emitted_player": deepcopy(self.emitted_player),
            "previous_platforms": deepcopy(self.previous_platforms),
            "player_dropout_streak": self.player_dropout_streak,
            "platform_dropout_streaks": dict(self.platform_dropout_streaks),
            "platform_priorities": dict(self.platform_priorities),
            "visible_target": self.visible_target,
            "last_diagnostics": deepcopy(self.last_diagnostics),
        }

    def load_state_dict(
        self,
        state: dict[str, Any],
        *,
        legacy_observation_timestamp: float | None = None,
        legacy_dt: float | None = None,
    ) -> None:
        self.rng.bit_generator.state = deepcopy(state["rng_state"])
        if "last_raw_player" in state:
            self.last_raw_player = deepcopy(state["last_raw_player"])
            self.last_raw_timestamp = (
                None if state["last_raw_timestamp"] is None else float(state["last_raw_timestamp"])
            )
            self.last_raw_velocity = {
                "x": float(state["last_raw_velocity"]["x"]),
                "y": float(state["last_raw_velocity"]["y"]),
            }
            self.last_raw_motion = str(state["last_raw_motion"])
            self.emitted_player = deepcopy(state.get("emitted_player"))
        else:
            # Portable curriculum snapshots created before the blocker fix did
            # not distinguish raw and emitted state. Preserve loadability with
            # an explicit conservative migration; new snapshots use the exact
            # raw-anchor schema above.
            legacy = deepcopy(state.get("previous_player"))
            legacy_streak = int(state.get("player_dropout_streak", 0))
            if legacy is not None and legacy_observation_timestamp is not None and legacy_dt is not None:
                elapsed = legacy_streak * legacy_dt
                self.last_raw_player = {
                    "center_x": float(legacy["center_x"]) - float(legacy["velocity_x"]) * elapsed,
                    "center_y": float(legacy["center_y"]) - float(legacy["velocity_y"]) * elapsed,
                }
                self.last_raw_timestamp = legacy_observation_timestamp - elapsed
            else:
                self.last_raw_player = legacy
                self.last_raw_timestamp = 0.0 if legacy is not None else None
            self.last_raw_velocity = {
                "x": 0.0 if legacy is None else float(legacy["velocity_x"]),
                "y": 0.0 if legacy is None else float(legacy["velocity_y"]),
            }
            self.last_raw_motion = "unknown"
            self.emitted_player = legacy
        self.previous_platforms = {int(k): deepcopy(v) for k, v in state["previous_platforms"].items()}
        self.player_dropout_streak = int(state["player_dropout_streak"])
        self.platform_dropout_streaks = {int(k): int(v) for k, v in state["platform_dropout_streaks"].items()}
        self.platform_priorities = {int(k): float(v) for k, v in state["platform_priorities"].items()}
        self.visible_target = None if state["visible_target"] is None else int(state["visible_target"])
        self.last_diagnostics = deepcopy(state["last_diagnostics"])

    def _quantized(self, value: float, quantum: float, noise: float) -> float:
        noisy = value + (float(self.rng.uniform(-noise, noise)) if noise else 0.0)
        return round(noisy / quantum) * quantum

    def _drop(self, streak: int, start: float, continuation: float, maximum: int) -> int:
        probability = continuation if streak else start
        return streak + 1 if streak < maximum and float(self.rng.random()) < probability else 0

    def _next_visible_target(self) -> int:
        if self.visible_target is None:
            self.visible_target = _categorical(self.rng, self.profile.visible_count_initial_pmf)
        else:
            self.visible_target = _categorical(self.rng, self.profile.visible_count_transition[self.visible_target])
        return self.visible_target

    def observe(self, clean: GameObservation, dt: float) -> GameObservation:
        if dt <= 0:
            raise ValueError("V3_OBSERVATION_DT")
        raw_player = clean.player
        timestamp = float(clean.timestamp)
        player = None
        raw_player_dropout = False
        previous_missing_streak = self.player_dropout_streak
        if raw_player is not None:
            self.player_dropout_streak = self._drop(
                self.player_dropout_streak,
                self.profile.player_dropout_start_probability,
                self.profile.player_dropout_continue_probability,
                self.profile.player_dropout_max_frames,
            )
            raw_player_dropout = self.player_dropout_streak > 0
        else:
            self.player_dropout_streak += 1
            raw_player_dropout = True

        recovery_elapsed: float | None = None
        recovery_from_dropout = False
        recovery_expected_velocity: dict[str, float] | None = None
        if raw_player_dropout:
            if (
                self.last_raw_player is not None
                and self.last_raw_timestamp is not None
                and self.player_dropout_streak <= self.profile.player_dropout_max_frames
                and timestamp >= self.last_raw_timestamp
            ):
                elapsed = timestamp - self.last_raw_timestamp
                x = self.last_raw_player["center_x"] + self.last_raw_velocity["x"] * elapsed
                y = self.last_raw_player["center_y"] + self.last_raw_velocity["y"] * elapsed
                vx = self.last_raw_velocity["x"]
                vy = self.last_raw_velocity["y"]
                motion = self.last_raw_motion
                player = {
                    "center_x": x, "center_y": y, "velocity_x": vx, "velocity_y": vy,
                    "motion": motion,
                    "confidence": 0.75 ** self.player_dropout_streak,
                    "detection_source": "tracked",
                    "missing_streak": self.player_dropout_streak,
                }
            else:
                # Match PlayerTracker reset semantics after the supported
                # recovery horizon; do not invent a velocity or tracked point.
                self.last_raw_player = None
                self.last_raw_timestamp = None
                self.last_raw_velocity = {"x": 0.0, "y": 0.0}
                self.last_raw_motion = "unknown"
        else:
            assert raw_player is not None
            x = self._quantized(float(raw_player["center_x"]), self.profile.player_center_quantum_px, self.profile.player_position_noise_uniform_px)
            y = self._quantized(float(raw_player["center_y"]), self.profile.player_center_quantum_px, self.profile.player_position_noise_uniform_px)
            if (
                self.last_raw_player is not None
                and self.last_raw_timestamp is not None
                and timestamp > self.last_raw_timestamp
            ):
                recovery_elapsed = timestamp - self.last_raw_timestamp
                vx = (x - self.last_raw_player["center_x"]) / recovery_elapsed
                vy = (y - self.last_raw_player["center_y"]) / recovery_elapsed
                if previous_missing_streak > 0:
                    recovery_expected_velocity = {"x": vx, "y": vy}
            else:
                vx = 0.0
                vy = 0.0
            motion = "falling" if vy > 5.0 else ("rising" if vy < -5.0 else ("stable" if recovery_elapsed is not None else "unknown"))
            recovery_from_dropout = previous_missing_streak > 0 and recovery_elapsed is not None
            player = {
                "center_x": x, "center_y": y, "velocity_x": vx, "velocity_y": vy,
                "motion": motion, "confidence": 1.0,
                "detection_source": "raw", "missing_streak": 0,
            }
            self.last_raw_player = {"center_x": x, "center_y": y}
            self.last_raw_timestamp = timestamp
            self.last_raw_velocity = {"x": vx, "y": vy}
            self.last_raw_motion = motion
            self.player_dropout_streak = 0
        self.emitted_player = deepcopy(player)

        candidates: list[dict[str, Any]] = []
        dropped_ids: set[int] = set()
        for raw in clean.platforms:
            track = int(raw["track_id"])
            streak = self._drop(
                self.platform_dropout_streaks.get(track, 0),
                self.profile.platform_track_dropout_start_probability,
                self.profile.platform_track_dropout_continue_probability,
                self.profile.platform_track_dropout_max_frames,
            )
            self.platform_dropout_streaks[track] = streak
            if streak:
                dropped_ids.add(track)
                continue
            self.platform_priorities.setdefault(track, float(self.rng.random()))
            box = dict(raw["box"])
            for key in ("left", "top"):
                box[key] = self._quantized(float(box[key]), self.profile.platform_box_quantum_px, self.profile.platform_position_noise_uniform_px)
            item = {**raw, "box": box, "kind": "conveyor" if str(raw["kind"]).startswith("conveyor_") else raw["kind"]}
            candidates.append(item)
        target = self._next_visible_target()
        player_y = float(player["center_y"]) if player else 0.0
        candidates.sort(key=lambda item: (
            abs(float(item["box"]["top"]) - player_y),
            self.platform_priorities[int(item["track_id"])],
        ))
        platforms = candidates[:target]
        current = {int(item["track_id"]): item for item in platforms}
        velocities = [
            (float(item["box"]["top"]) - float(self.previous_platforms[track]["box"]["top"])) / dt
            for track, item in current.items() if track in self.previous_platforms
        ]
        scroll = float(np.median(velocities)) if velocities else self.profile.no_match_scroll_value_px_s
        self.previous_platforms = deepcopy(current)
        nearest = clean.nearest_platform
        nearest_result = None
        if nearest is not None and int(nearest["track_id"]) in current:
            nearest_result = {**current[int(nearest["track_id"])], "vertical_gap": nearest.get("vertical_gap")}
        self.last_diagnostics = {
            "player_raw_dropout": raw_player_dropout,
            "player_dropout_streak": self.player_dropout_streak,
            "player_recovery_from_dropout": recovery_from_dropout,
            "player_recovery_raw_elapsed": recovery_elapsed,
            "player_recovery_expected_velocity": recovery_expected_velocity,
            "player_tracking_phase": (
                "missing" if player is None else str(player["detection_source"])
            ),
            "platform_track_dropouts": len(dropped_ids),
            "visible_platforms": len(platforms), "visible_target": target,
            "matched_platforms": len(velocities), "scroll_no_match": not velocities,
            "dt": dt,
        }
        return replace(
            clean, player=player, platforms=platforms, nearest_platform=nearest_result,
            platform_scroll_velocity_y=scroll,
        )


class FidelityV3Env(ShaftEnv):
    """V3-only env preserving the 64-D/4-frame/3-action 268-D contract."""

    def __init__(self, *, profile: FidelityV3Profile, base_seed: int = 42, forced_fps: int | None = None, render_mode: str | None = None) -> None:
        self.v3_profile = profile
        self.profile = profile.parent
        self.base_seed = int(base_seed)
        self.episode_index = 0
        self.episode_seed = self.base_seed
        self.forced_fps = forced_fps
        self.cadence_hz = 8
        self.derived_seeds: dict[str, int] = {}
        self.episode_parameters: dict[str, float] = {}
        self.layout_diagnostics: list[dict[str, Any]] = []
        self._observation_rng = np.random.default_rng(base_seed)
        self.observation_emulator = RealStyleObservationEmulator(profile.observation, self._observation_rng)
        super().__init__(config=profile.parent.nominal_config(environment_version=FIDELITY_V3_VERSION, fps=8), render_mode=render_mode)

    def _sample_config(self, fps: int) -> Any:
        rng = np.random.default_rng(self.derived_seeds["physics_dr_seed"])
        sampled = {name: float(rng.uniform(low, high)) for name, (low, high) in self.profile.ranges.items()}
        sampled["platform_width"] = float(rng.uniform(*self.v3_profile.layout.width_range))
        special_rng = np.random.default_rng(self.derived_seeds["special_seed"])
        envelope = self.v3_profile.layout_raw["special_probability_envelope"]
        sampled.update({
            "spike_spawn_probability": float(special_rng.uniform(*envelope["spikes"])),
            "spring_spawn_probability": float(special_rng.uniform(*envelope["spring"])),
            "conveyor_spawn_probability": float(special_rng.uniform(*envelope["conveyor_combined"])),
            "flipping_spawn_probability": float(special_rng.uniform(*envelope["flipping"])),
        })
        self.episode_parameters = dict(sampled)
        return replace(
            self.profile.nominal_config(environment_version=FIDELITY_V3_VERSION, fps=fps),
            **sampled, platform_spacing=48.0,
            platform_count=int(self.v3_profile.layout_raw["physical_platform_count"]),
        )

    def _choose_cadence(self) -> int:
        if self.forced_fps is not None:
            if self.forced_fps not in (8, 10, 12):
                raise ValueError("V3_FORCED_FPS")
            return int(self.forced_fps)
        return _categorical(np.random.default_rng(self.derived_seeds["cadence_seed"]), self.v3_profile.cadence_probabilities)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        del options
        if seed is not None:
            self.base_seed = int(seed)
            self.episode_index = 0
        self.episode_seed = self.base_seed + self.episode_index
        self.episode_index += 1
        self.derived_seeds = derive_v3_seeds(self.episode_seed)
        self.cadence_hz = self._choose_cadence()
        super(ShaftEnv, self).reset(seed=self.episode_seed)
        self.config = self._sample_config(self.cadence_hz)
        self.reward_calculator = SimulatorRewardCalculator(self.config)
        self._observation_rng = np.random.default_rng(self.derived_seeds["observation_seed"])
        self.observation_emulator = RealStyleObservationEmulator(self.v3_profile.observation, self._observation_rng)
        self._step_count = 0
        self.simulator = FidelityV3Simulator(self.config, np.random.default_rng(self.derived_seeds["layout_seed"]), self.v3_profile.layout)
        self.layout_diagnostics = deepcopy(self.simulator.layout_diagnostics)
        self._diagnostics = {}
        clean = ShaftEnv._game_observation(self)
        self.last_observation = self.observation_emulator.observe(clean, self.config.dt)
        return self.temporal_stack.reset(self.encoder.encode(self.last_observation)), self._info()

    def _game_observation(self, *, events: tuple[str, ...] = (), terminated: bool = False) -> GameObservation:
        clean = ShaftEnv._game_observation(self, events=events, terminated=terminated)
        return self.observation_emulator.observe(clean, self.config.dt)

    def _info(self, **kwargs: Any) -> dict[str, Any]:
        info = ShaftEnv._info(self, **kwargs)
        info.update({
            "fidelity_version": FIDELITY_V3_VERSION,
            "episode_seed": self.episode_seed, "cadence_hz": self.cadence_hz,
            "causal_dt": self.config.dt, "physics_frequency_hz": self.config.physics_hz,
            "episode_parameters": dict(self.episode_parameters),
            "observation_emulator": deepcopy(self.observation_emulator.last_diagnostics),
            **self.derived_seeds,
        })
        return info

    def capture_portable_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "fidelity-v3-snapshot-v1",
            "episode_seed": self.episode_seed,
            "cadence_hz": self.cadence_hz,
            "base_snapshot": env_snapshot_to_portable_dict(capture_env(self)),
            "emulator_state": self.observation_emulator.state_dict(),
        }

    def restore_portable_snapshot(self, payload: dict[str, Any]) -> np.ndarray:
        if payload.get("schema_version") != "fidelity-v3-snapshot-v1":
            raise ValueError("V3_SNAPSHOT_SCHEMA")
        cadence = int(payload["cadence_hz"])
        prior_forced = self.forced_fps
        self.forced_fps = cadence
        self.reset(seed=int(payload["episode_seed"]))
        self.forced_fps = prior_forced
        result = restore_env(self, portable_dict_to_env_snapshot(payload["base_snapshot"]))
        self.observation_emulator.load_state_dict(
            payload["emulator_state"],
            legacy_observation_timestamp=self._step_count * self.config.dt,
            legacy_dt=self.config.dt,
        )
        return result


def make_fidelity_v3_env(profile_path: str | Path, *, base_seed: int, forced_fps: int | None = None) -> FidelityV3Env:
    return FidelityV3Env(profile=load_fidelity_v3_profile(profile_path), base_seed=base_seed, forced_fps=forced_fps)


__all__ = [
    "FIDELITY_V3_VERSION", "FidelityV3Env", "FidelityV3Profile",
    "ObservationEmulatorProfile", "RealStyleObservationEmulator",
    "derive_v3_seeds", "load_fidelity_v3_profile", "make_fidelity_v3_env",
]
