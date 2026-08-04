from __future__ import annotations

from stair_agent.learnability import (
    evaluate_candidate,
    random_selector,
    release_selector,
)


def test_release_evaluation_reports_action_collapse_and_hard_step_limit():
    result = evaluate_candidate(
        "release",
        release_selector,
        seeds=[1, 2],
        max_episode_steps=5,
    )

    assert result.episodes == 2
    assert result.total_steps <= 10
    assert result.action_counts["RELEASE_ALL"] == result.total_steps
    assert result.max_action_share == 1.0
    assert result.collapsed
    assert all(
        episode.deepest_floor >= episode.floors
        for episode in result.episode_results
    )


def test_random_evaluation_is_seed_reproducible():
    first = evaluate_candidate(
        "random",
        random_selector,
        seeds=[11, 12],
        max_episode_steps=8,
    )
    second = evaluate_candidate(
        "random",
        random_selector,
        seeds=[11, 12],
        max_episode_steps=8,
    )

    assert first.to_dict() == second.to_dict()
    assert sum(first.action_counts.values()) == first.total_steps


def test_direction_reversals_bridge_release_actions() -> None:
    actions = iter((1, 0, 0, 2, 0, 1))

    def selector(_observation, _env, _rng):
        return next(actions)

    result = evaluate_candidate(
        "release-bridged-reversal",
        selector,
        seeds=[123],
        max_episode_steps=6,
    )

    assert result.total_steps == 6
    assert result.direction_switches == 0
    assert result.direction_reversals == 2


def test_evaluate_candidate_aggregates_episode_event_counts() -> None:
    result = evaluate_candidate(
        "release-events",
        release_selector,
        seeds=[1, 2],
        max_episode_steps=40,
    )
    summed = sum(
        episode.event_counts.get("landed", 0)
        for episode in result.episode_results
    )
    assert result.event_counts.get("landed", 0) == summed
