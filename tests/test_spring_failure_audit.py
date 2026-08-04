from __future__ import annotations

from stair_agent.training.spring_failure_audit import (
    analyze_real_spring_evidence,
    trace_oracle_spring_failures,
)
from stair_agent.training.spring_curriculum_gate import spring_curriculum_config


def test_failure_trace_proves_repeated_contact_precedes_top_death() -> None:
    result = trace_oracle_spring_failures(
        [10007],
        config=spring_curriculum_config(),
        max_episode_steps=120,
    )
    episode = result["episodes"][0]
    assert episode["terminal_reason"] == "top"
    assert episode["spring_contact_count"] >= 2
    assert not episode["top_on_first_spring_bounce"]
    assert episode["post_first_contact_action_counts"]["RELEASE_ALL"] > 0
    assert result["hypotheses"]["single_bounce_direct_top_death"] is False
    assert result["hypotheses"]["repeated_contact_before_top_death"] is True


def test_real_spring_evidence_does_not_treat_visibility_as_contact() -> None:
    records = [
        {
            "observation": {
                "nearest_platform": {"kind": "spring"},
                "platforms": [{"kind": "spring"}],
            },
            "next_observation": {
                "nearest_platform": {"kind": "normal"},
                "platforms": [],
            },
            "teacher": {"target_platform_kind": "spring"},
            "events": [],
        },
        {
            "observation": {
                "nearest_platform": {"kind": "normal"},
                "platforms": [],
            },
            "next_observation": {
                "nearest_platform": {"kind": "normal"},
                "platforms": [],
            },
            "teacher": {"target_platform_kind": "normal"},
            "events": [
                {
                    "type": "spring_bounce",
                    "source_platform_kind": "spring",
                }
            ],
        },
    ]
    result = analyze_real_spring_evidence(records)
    assert result["spring_visible_records"] == 1
    assert result["spring_target_records"] == 1
    assert result["confirmed_spring_event_records"] == 1
    assert result["physics_calibration_eligible"] is False
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
