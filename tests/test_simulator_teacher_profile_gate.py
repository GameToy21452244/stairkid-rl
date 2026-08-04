from stair_agent.policies.simulator_teachers import SIMULATOR_TEACHER_PROFILES
from stair_agent.training.simulator_teacher_profile_gate import (
    evaluate_fresh_reliability,
    evaluate_simulator_teacher_profile,
    select_same_seed_candidate,
)


def test_profile_evaluation_is_bounded_and_carries_version() -> None:
    profile = SIMULATOR_TEACHER_PROFILES[
        "departure_delayed_launch_handoff"
    ]

    observed = []
    result = evaluate_simulator_teacher_profile(
        profile,
        range(9100, 9106),
        decision_observer=lambda seed, step, observation, decision, env: (
            observed.append(
                (
                    seed,
                    step,
                    observation.phase,
                    decision.policy_version,
                    env.simulator.deepest_floor,
                )
            )
        ),
    )

    assert result["performance"]["episodes"] == 6
    assert result["analysis"]["policy_versions"] == [profile.policy_version]
    assert result["analysis"]["path"].startswith("diagnostic://")
    assert len(result["deepest_floor_by_seed"]) == 6
    assert len(observed) == result["analysis"]["records"]
    assert observed[0][:4] == (9100, 0, "playing", profile.policy_version)


def test_selection_uses_only_passing_candidates_and_risk_first() -> None:
    def candidate(passed, bottom, q25):
        return {
            "same_seed_gate": {"passed": passed},
            "performance": {
                "health_death_rate": 0.0,
                "bottom_death_rate": bottom,
                "deepest_floor_quantile_25": q25,
                "deepest_floor_cvar25": q25,
                "reach_floor_10_rate": 0.95,
                "release_bridged_reversals_per_100_steps": 5.0,
                "median_deepest_floor": 10.0,
                "mean_deepest_floor": 10.0,
            },
        }

    selected = select_same_seed_candidate(
        {
            "failed": candidate(False, 0.0, 12.0),
            "safer": candidate(True, 0.05, 9.0),
            "higher_q25": candidate(True, 0.08, 11.0),
        }
    )

    assert selected == "safer"


def test_fresh_gate_requires_exactly_100_episodes() -> None:
    gate = evaluate_fresh_reliability(
        {
            "performance": {
                "episodes": 99,
                "reach_floor_10_rate": 1.0,
                "bottom_death_rate": 0.0,
                "health_death_rate": 0.0,
                "deepest_floor_quantile_25": 10.0,
                "deepest_floor_cvar25": 10.0,
            }
        }
    )

    assert not gate["passed"]
    assert not gate["checks"]["episode_count_100"]
