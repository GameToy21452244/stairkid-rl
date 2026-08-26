from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from .fidelity_v3 import FidelityV3Env, FidelityV3Profile
from .fidelity_v3_fresh import load_fidelity_v3_fresh_profile

V35_SCHEMA_VERSION = "stairkid-v3-5-safety-refinement-v1"
V35_STRATEGY_VERSION = "fresh-v3-safety-refinement-r4-edge-sign-corrected-flipping-v1"
V35_PARENT_SHA256 = "e539ad8e9a39991d738ef9d4113968d933d4f2535e3b08fabe27f3b4ffd9f51e"
V35_INITIALIZATION = "TRANSFER_FROM_LEGACY_FLIPPING_PARENT"
V35_CORRECTED_PHYSICS_COMMIT = "0cb23aca7dcb112b2c49347a4777b4234d4ead92"
V35_AUDITED_LOCAL_FIX_COMMIT = "0d70ba63f534bfddf1268a995275f6cb8b210a51"
V35_CORRECTED_BASELINE_EVALUATION_COMMIT = "e0ea06e2d35f0533fc9b267a648ae01c7cb60e7a"
V35_R4_POSTMORTEM_FINDING = "FAILURE_LANDING_REWARD_SIGN_MISALIGNMENT"
V35_R4_STOP_RULE = "If R4 does not produce a DEV64 candidate that passes the existing corrected absolute gates, stop V3.5 permanently; no R5."


@dataclass(frozen=True)
class V35RewardProfile:
    step_penalty: float = 0.003
    landing_reward: float = 0.05
    floor_reward: float = 1.0
    death_penalty: float = 5.0
    spike_damage_penalty_per_segment: float = 0.75
    health_gain_reward_per_segment: float = 0.05
    safe_landing_bonus: float = 0.30
    safe_landing_margin: float = 14.0
    edge_landing_penalty: float = 1.10


@dataclass(frozen=True)
class V35Profile:
    path: Path
    fresh_profile_path: Path
    fresh_profile: FidelityV3Profile
    reward: V35RewardProfile
    raw: dict[str, Any]


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"V35_{name}_MUST_BE_MAPPING")
    return value


def _require_exact(mapping: dict[str, Any], expected: dict[str, Any], name: str) -> None:
    for key, value in expected.items():
        if mapping.get(key) != value:
            raise ValueError(f"V35_{name}_CONTRACT_MISMATCH:{key}:{mapping.get(key)!r}!={value!r}")


def _resolve_profile_path(contract_path: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (contract_path.parent.parent / candidate).resolve()


def load_fidelity_v3_5_profile(path: str | Path) -> V35Profile:
    contract_path = Path(path).resolve()
    raw = _mapping(yaml.safe_load(contract_path.read_text(encoding="utf-8")), "PROFILE")
    if raw.get("schema_version") != V35_SCHEMA_VERSION:
        raise ValueError("V35_SCHEMA_VERSION_MISMATCH")
    if raw.get("strategy_version") != V35_STRATEGY_VERSION:
        raise ValueError("V35_STRATEGY_VERSION_MISMATCH")

    lineage = _mapping(raw.get("lineage"), "LINEAGE")
    _require_exact(
        lineage,
        {
            "initialization": V35_INITIALIZATION,
            "parent_training_physics": "legacy_defective_flipping_runtime_state",
            "refinement_physics": "corrected_flipping_runtime_state_v1",
            "corrected_physics_commit": V35_CORRECTED_PHYSICS_COMMIT,
            "audited_local_fix_commit": V35_AUDITED_LOCAL_FIX_COMMIT,
            "corrected_baseline_evaluation_commit": V35_CORRECTED_BASELINE_EVALUATION_COMMIT,
            "parent_role": "PRIMARY_FROZEN_BASELINE_AND_TRAINING_PARENT",
            "parent_sha256": V35_PARENT_SHA256,
            "parent_timesteps": 524_288,
            "legacy_bank_training_share": 0.0,
        },
        "LINEAGE",
    )

    reward_raw = _mapping(raw.get("reward"), "REWARD")
    reward = V35RewardProfile(
        step_penalty=float(reward_raw.get("step_penalty", -1)),
        landing_reward=float(reward_raw.get("landing_reward", -1)),
        floor_reward=float(reward_raw.get("floor_reward", -1)),
        death_penalty=float(reward_raw.get("death_penalty", -1)),
        spike_damage_penalty_per_segment=float(reward_raw.get("spike_damage_penalty_per_segment", -1)),
        health_gain_reward_per_segment=float(reward_raw.get("health_gain_reward_per_segment", -1)),
        safe_landing_bonus=float(reward_raw.get("safe_landing_bonus", -1)),
        safe_landing_margin=float(reward_raw.get("safe_landing_margin", -1)),
        edge_landing_penalty=float(reward_raw.get("edge_landing_penalty", -1)),
    )
    if reward != V35RewardProfile():
        raise ValueError(f"V35_REWARD_CONTRACT_MISMATCH:{reward}")
    if float(reward_raw.get("spike_safe_landing_bonus", -1)) != 0.0:
        raise ValueError("V35_LANDING_SHAPING_CONTRACT_MISMATCH")

    r4_hypothesis = _mapping(raw.get("r4_hypothesis"), "R4_HYPOTHESIS")
    _require_exact(
        r4_hypothesis,
        {
            "source_postmortem": "analysis/v3-5-r3-postmortem-v1",
            "primary_finding": V35_R4_POSTMORTEM_FINDING,
            "single_changed_training_variable": "edge_landing_penalty",
            "previous_value": 0.10,
            "new_value": 1.10,
            "edge_event_net_no_heal": -0.053,
            "edge_event_net_one_heal": -0.003,
            "final_v35_round": True,
            "frozen_r1_input_bundle_sha256": "3b8e85d52d94b11cacf1466019558670791471a190d79b80ed18a62985b7f53e",
            "reuse_exact_r3_r1_checkpoints_and_banks": True,
            "r1_retraining_forbidden": True,
            "bank_recollection_forbidden": True,
            "stop_rule": V35_R4_STOP_RULE,
        },
        "R4_HYPOTHESIS",
    )

    training = _mapping(raw.get("training"), "TRAINING")
    _require_exact(
        training,
        {
            "train_seeds": [117, 142],
            "parent_timesteps": 524_288,
            "stage_r1_end": 589_824,
            "stage_r2_mid": 655_360,
            "stage_r2_end": 720_896,
            "checkpoint_targets": [589_824, 655_360, 720_896],
            "r1_schedule": ["ordinary"],
            "r2_schedule": ["ordinary", "ordinary", "failure", "success"],
            "n_envs": 4,
            "n_steps": 1024,
            "batch_size": 256,
            "n_epochs": 10,
            "learning_rate": 0.0003,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "vf_coef": 0.5,
            "max_grad_norm": 0.5,
        },
        "TRAINING",
    )

    curriculum = _mapping(raw.get("curriculum"), "CURRICULUM")
    _require_exact(
        curriculum,
        {
            "schema_version": "v3-5-targeted-safety-bank-r3-corrected-flipping-v1",
            "corrected_physics_commit": V35_CORRECTED_PHYSICS_COMMIT,
            "source_stage": "R1",
            "risk_total": 48,
            "risk_counts": {"landing": 20, "spike": 20, "top": 8},
            "success_total": 48,
            "lookback_steps": {"landing": 3, "spike": 5, "top": 3},
            "landing_priority": "edge_landing_first_with_miss_or_bottom_fallback",
            "spike_priority": "first_damage_event_per_episode",
            "per_episode_caps": {"landing": 1, "spike": 1, "top": 1, "success": 1},
            "success_min_floor": 5,
            "success_requires_safe_landing": True,
            "collection_max_episodes": 1024,
            "contains_legacy_entries": False,
            "runtime_schedule": ["ordinary", "ordinary", "failure", "success"],
            "runtime_schedule_semantics": "fixed_vector_lane_timestep_quota",
            "failure_horizon_steps": 12,
            "success_horizon_steps": 8,
            "risk_runtime_cycle": ["landing", "spike", "landing", "spike", "top"],
        },
        "CURRICULUM",
    )

    evaluation = _mapping(raw.get("evaluation"), "EVALUATION")
    _require_exact(
        evaluation,
        {
            "physical_seconds": 30.0,
            "dev_seeds": {"start": 50_000_000, "count": 64},
            "final_seeds": {"start": 60_000_000, "count": 200},
            "final_holdout_max_candidates": 1,
            "final_holdout_reselection_after_attempt": False,
            "metric_definitions": {
                "spike_contact_episode_rate": "episodes_with_spike_contact / episodes",
                "damage_segments_per_episode": "total_negative_health_delta_segments / episodes",
                "health_depleted_death_rate": "health_depleted_terminals / episodes",
                "bottom_death_rate": "bottom_terminals / episodes",
                "top_death_rate": "top_terminals / episodes",
                "safe_landing_rate": "safe_non_spike_landings / classified_non_spike_landings",
                "edge_landing_rate": "edge_non_spike_landings / classified_non_spike_landings",
                "steps_per_descended_floor": "total_policy_steps / max(total_deepest_floor, 1)",
            },
            "development_gate": {
                "mean_ratio_min": 0.95,
                "p25_delta_min": 0.0,
                "floor_le4_delta_max": 0.0,
                "damage_segments_ratio_max": 0.75,
                "bottom_death_rate_ratio_max": 0.85,
                "top_death_rate_delta_max": 0.0,
                "safe_landing_rate_delta_min": 0.05,
                "steps_per_descended_floor_ratio_max": 1.5,
            },
            "corrected_parent_dev_reference": {
                "model_sha256": V35_PARENT_SHA256,
                "model_timesteps": 524_288,
                "seed_start": 50_000_000,
                "seed_count": 64,
                "mean": 30.6875,
                "q25": 16.75,
                "median": 29.0,
                "floor_le4_rate": 0.03125,
                "damage_segments_per_episode": 5.3125,
                "bottom_death_rate": 0.3125,
                "top_death_rate": 0.359375,
                "safe_landing_rate": 0.6819787985865724,
                "steps_per_descended_floor": 5.609979633401222,
            },
            "absolute_development_gate": {
                "mean_min": 29.153125,
                "q25_min": 16.75,
                "floor_le4_rate_max": 0.03125,
                "damage_segments_per_episode_max": 3.984375,
                "bottom_death_rate_max": 0.265625,
                "top_death_rate_max": 0.359375,
                "safe_landing_rate_min": 0.7319787985865724,
                "steps_per_descended_floor_max": 8.414969450101832,
            },
        },
        "EVALUATION",
    )

    safety = _mapping(raw.get("safety"), "SAFETY")
    _require_exact(
        safety,
        {
            "observation_shape": [268],
            "action_space": "Discrete(3)",
            "actions": ["RELEASE_ALL", "LEFT", "RIGHT"],
            "safe_action_mask_policy_input": False,
            "real_game_execution": "FORBIDDEN",
            "automatic_promotion": False,
        },
        "SAFETY",
    )

    fresh_path = _resolve_profile_path(contract_path, str(raw.get("fresh_profile")))
    return V35Profile(
        path=contract_path,
        fresh_profile_path=fresh_path,
        fresh_profile=load_fidelity_v3_fresh_profile(fresh_path),
        reward=reward,
        raw=raw,
    )


def classify_landing(
    *,
    platform_kind: str,
    impact_x: float,
    platform_left: float,
    platform_right: float,
    safe_margin: float,
) -> str:
    if platform_kind == "spikes":
        return "spike"
    if platform_left + safe_margin <= impact_x <= platform_right - safe_margin:
        return "safe"
    return "edge"


class FidelityV35Env(FidelityV3Env):
    """V3.5 round-3 safety refinement; observation/action/physics remain Fresh V3."""

    def __init__(
        self,
        *,
        profile: V35Profile,
        base_seed: int = 42,
        forced_fps: int | None = None,
        render_mode: str | None = None,
    ) -> None:
        self.v35_profile = profile
        super().__init__(
            profile=profile.fresh_profile,
            base_seed=base_seed,
            forced_fps=forced_fps,
            render_mode=render_mode,
        )

    def _sample_config(self, fps: int) -> Any:
        config = super()._sample_config(fps)
        reward = self.v35_profile.reward
        return replace(
            config,
            step_penalty=reward.step_penalty,
            landing_reward=reward.landing_reward,
            floor_reward=reward.floor_reward,
            death_penalty=reward.death_penalty,
            spike_damage_penalty_per_segment=reward.spike_damage_penalty_per_segment,
            health_gain_reward_per_segment=reward.health_gain_reward_per_segment,
            safe_landing_margin=reward.safe_landing_margin,
        )

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        pre_step_platforms: dict[int, dict[str, Any]] = {}
        if self.simulator is not None:
            pre_step_platforms = {
                int(item.floor_index): {
                    "kind": str(item.kind),
                    "left": float(item.left),
                    "right": float(item.right),
                }
                for item in self.simulator.platforms
            }

        observation, reward, terminated, truncated, info = super().step(action)
        events = [str(value) for value in info.get("events", [])]
        reward_components = dict(info.get("reward_components", {}))
        reward_components.setdefault("safe_landing_bonus", 0.0)
        reward_components.setdefault("edge_landing_penalty", 0.0)
        landing_safety: dict[str, Any] | None = None

        if "landed" in events:
            diagnostic = info.get("collision_diagnostic")
            if not isinstance(diagnostic, dict) or diagnostic.get("decision") != "landed":
                landing_safety = {
                    "classification": "unknown",
                    "reliable": False,
                    "reason": "missing_or_non_landed_collision_diagnostic",
                }
            else:
                try:
                    floor = int(diagnostic["platform_floor"])
                    impact_x = float(diagnostic["impact_x"])
                except (KeyError, TypeError, ValueError):
                    landing_safety = {
                        "classification": "unknown",
                        "reliable": False,
                        "reason": "invalid_landing_collision_diagnostic",
                    }
                else:
                    geometry = pre_step_platforms.get(floor)
                    geometry_source = "pre_step_platform_snapshot"
                    if geometry is None and self.simulator is not None:
                        platform = next(
                            (item for item in self.simulator.platforms if int(item.floor_index) == floor),
                            None,
                        )
                        if platform is not None:
                            geometry = {
                                "kind": str(platform.kind),
                                "left": float(platform.left),
                                "right": float(platform.right),
                            }
                            geometry_source = "post_step_platform_fallback"
                    if geometry is None:
                        landing_safety = {
                            "classification": "unknown",
                            "platform_floor": floor,
                            "impact_x": impact_x,
                            "safe_landing_margin": float(self.config.safe_landing_margin),
                            "reliable": False,
                            "reason": "landing_platform_geometry_unavailable",
                        }
                    else:
                        kind = str(geometry["kind"])
                        diagnostic_kind = diagnostic.get("platform_kind")
                        if diagnostic_kind is not None and str(diagnostic_kind) != kind:
                            landing_safety = {
                                "classification": "unknown",
                                "platform_floor": floor,
                                "impact_x": impact_x,
                                "safe_landing_margin": float(self.config.safe_landing_margin),
                                "reliable": False,
                                "reason": "landing_platform_kind_mismatch",
                            }
                        else:
                            left = float(geometry["left"])
                            right = float(geometry["right"])
                            zone = classify_landing(
                                platform_kind=kind,
                                impact_x=impact_x,
                                platform_left=left,
                                platform_right=right,
                                safe_margin=float(self.config.safe_landing_margin),
                            )
                            landing_safety = {
                                "classification": zone,
                                "platform_floor": floor,
                                "platform_kind": kind,
                                "impact_x": impact_x,
                                "platform_left": left,
                                "platform_right": right,
                                "safe_landing_margin": float(self.config.safe_landing_margin),
                                "geometry_source": geometry_source,
                                "reliable": True,
                            }
                            if zone == "safe":
                                bonus = float(self.v35_profile.reward.safe_landing_bonus)
                                reward += bonus
                                reward_components["safe_landing_bonus"] = bonus
                                events.append("safe_landing")
                            elif zone == "edge":
                                penalty = float(self.v35_profile.reward.edge_landing_penalty)
                                reward -= penalty
                                reward_components["edge_landing_penalty"] = -penalty
                                events.append("edge_landing")
                            else:
                                events.append("spike_landing")

        info["events"] = events
        info["landing_safety"] = landing_safety
        info["reward_components"] = reward_components
        info["v3_5_safety_refinement"] = True
        info["safe_landing_bonus"] = float(self.v35_profile.reward.safe_landing_bonus)
        info["edge_landing_penalty"] = float(self.v35_profile.reward.edge_landing_penalty)
        self.reward_calculator.last_components = reward_components
        if isinstance(self._diagnostics, dict):
            self._diagnostics["reward"] = round(float(reward), 4)
            self._diagnostics["reward_components"] = dict(reward_components)
            self._diagnostics["landing_safety"] = landing_safety
        return observation, float(reward), terminated, truncated, info


def make_fidelity_v3_5_env(
    profile_path: str | Path,
    *,
    base_seed: int,
    forced_fps: int | None = None,
) -> FidelityV35Env:
    return FidelityV35Env(
        profile=load_fidelity_v3_5_profile(profile_path),
        base_seed=base_seed,
        forced_fps=forced_fps,
    )


__all__ = [
    "FidelityV35Env",
    "V35Profile",
    "V35RewardProfile",
    "V35_PARENT_SHA256",
    "V35_SCHEMA_VERSION",
    "V35_INITIALIZATION",
    "V35_CORRECTED_PHYSICS_COMMIT",
    "V35_AUDITED_LOCAL_FIX_COMMIT",
    "V35_CORRECTED_BASELINE_EVALUATION_COMMIT",
    "V35_STRATEGY_VERSION",
    "classify_landing",
    "load_fidelity_v3_5_profile",
    "make_fidelity_v3_5_env",
]
