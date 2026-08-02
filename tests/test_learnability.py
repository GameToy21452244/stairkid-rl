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
