from __future__ import annotations

import json
from pathlib import Path

import pytest

from stair_agent.input_controller import Action
from stair_agent.simulator.manual_test import (
    MANUAL_SEED_MINIMUM,
    ManualInputState,
    ManualSimulatorSession,
    build_manual_environment,
    list_manual_scenarios,
    run_headless_smoke,
    validate_manual_seed,
)


EXPECTED_SCENARIOS = {
    "normal_baseline",
    "horizontal_acceleration",
    "release_damping",
    "reverse_braking",
    "platform_edge_departure",
    "landing_support",
    "top_terminal",
    "bottom_terminal",
    "spring",
    "conveyor_left",
    "conveyor_right",
    "spikes",
    "flipping_active",
    "flipping_inactive",
    "normal_healing",
}


def test_manual_seed_partition_rejects_all_formal_ranges() -> None:
    assert validate_manual_seed(MANUAL_SEED_MINIMUM) == MANUAL_SEED_MINIMUM
    for seed in (6000, 8000, 13000, 16000, 17000, 18000, 18100, 19000):
        with pytest.raises(ValueError, match="manual-only"):
            validate_manual_seed(seed)


def test_fixed_scenario_catalog_is_complete_and_marks_specials_provisional() -> None:
    scenarios = list_manual_scenarios()
    assert {item.name for item in scenarios} == EXPECTED_SCENARIOS
    assert [item.scenario_id for item in scenarios] == [
        f"M{index:02d}" for index in range(1, 16)
    ]
    special = [item for item in scenarios if item.special_platform]
    assert special
    assert all(item.validation_status == "PROVISIONAL" for item in special)
    assert all(item.formal_evaluation_allowed is False for item in scenarios)


@pytest.mark.parametrize("scenario", sorted(EXPECTED_SCENARIOS))
def test_every_manual_scenario_builds_without_formal_seed_use(
    scenario: str,
) -> None:
    env, definition = build_manual_environment(
        scenario,
        seed=MANUAL_SEED_MINIMUM,
    )
    try:
        assert env.simulator is not None
        assert definition.formal_evaluation_allowed is False
        assert env.config.environment_version == (
            "ns-shaft-sim-v0.4-calibration-candidate"
        )
    finally:
        env.close()


def test_keyboard_state_maps_local_directions_and_focus_loss_to_release() -> None:
    state = ManualInputState()
    assert state.action is Action.RELEASE_ALL
    state.key_down("a")
    assert state.action is Action.LEFT
    state.key_up("a")
    state.key_down("right")
    assert state.action is Action.RIGHT
    state.key_down("left")
    assert state.action is Action.RELEASE_ALL
    state.focus_lost()
    assert state.action is Action.RELEASE_ALL
    assert state.held_keys == frozenset()


def test_session_controls_reset_pause_switch_overlay_and_record_logs(
    tmp_path: Path,
) -> None:
    session = ManualSimulatorSession(
        scenario="horizontal_acceleration",
        seed=MANUAL_SEED_MINIMUM,
        output_root=tmp_path,
        session_id="unit-session",
        show_debug=True,
    )
    try:
        original = session.scenario.name
        session.input_state.key_down("d")
        row = session.step_once()
        assert row["action"] == "RIGHT"
        session.toggle_pause()
        assert session.paused
        session.toggle_pause()
        session.toggle_debug()
        assert not session.show_debug
        session.reset_scenario()
        assert session.step_count == 0
        session.next_scenario()
        assert session.scenario.name != original
        session.toggle_calibration_profile()
        assert session.calibration_profile == "before"
        assert session.env.config.environment_version == "ns-shaft-sim-v0.3"
        session.add_rating(
            rating="close",
            tags=["visual_only_difference"],
            note="manual note",
            calibration_answers={
                "horizontal_acceleration_closer": "close",
            },
        )
    finally:
        output_dir = session.close()

    expected = {
        "session_summary.json",
        "frame_or_step_log.csv",
        "manual_ratings.json",
        "README.md",
        "events.json",
    }
    assert expected <= {path.name for path in output_dir.iterdir()}
    summary = json.loads(
        (output_dir / "session_summary.json").read_text(encoding="utf-8")
    )
    assert summary["formal_evidence"] is False
    assert summary["manual_alignment_only"] is True
    assert summary["seed_role"] == "manual_only"
    assert summary["formal_evaluation_allowed"] is False


def test_headless_smoke_exercises_controls_without_game_or_training(
    tmp_path: Path,
) -> None:
    result = run_headless_smoke(
        output_root=tmp_path,
        seed=MANUAL_SEED_MINIMUM + 1,
        steps=5,
    )
    assert result["status"] == "PASS_HEADLESS_MANUAL_SMOKE"
    assert result["game_input_used"] is False
    assert result["training_started"] is False
    assert result["holdout_used"] is False
    output_dir = Path(result["output_dir"])
    assert (output_dir / "session_summary.json").exists()
    assert result["checks"] == {
        "focus_loss_releases": True,
        "logging_writes": True,
        "overlay_toggles": True,
        "pause_toggles": True,
        "reset_works": True,
        "scenario_switches": True,
    }
