from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.simulator.calibration_review import (
    collision_diagnostics,
    fps_invariance,
    layout_distribution,
)
from stair_agent.simulator.generator import (
    next_platform_center_with_diagnostics,
)
from stair_agent.simulator.manual_test import calibration_profile_config
from stair_agent.simulator.state import ShaftEnvConfig


def _candidate_config(**changes: object) -> ShaftEnvConfig:
    return replace(
        calibration_profile_config(ShaftEnvConfig(), "after"),
        **changes,
    )


def _stand_on_first(env: ShaftEnv, *, velocity_x: float = 0.0) -> None:
    simulator = env.simulator
    assert simulator is not None
    platform = min(simulator.platforms, key=lambda item: item.floor_index)
    simulator.supported_floor = platform.floor_index
    simulator.player.body.position = (
        platform.center_x,
        platform.top + simulator.player.height / 2,
    )
    simulator.player.body.velocity = (
        velocity_x,
        simulator.config.scroll_speed,
    )


def test_v04_candidate_exposes_separate_calibration_parameters() -> None:
    config = _candidate_config()
    assert config.environment_version == "ns-shaft-sim-v0.4-calibration-candidate"
    assert config.horizontal_acceleration == pytest.approx(560.0)
    assert config.air_control_multiplier == pytest.approx(0.85)
    assert config.max_horizontal_speed == pytest.approx(230.0)
    assert config.release_deceleration == pytest.approx(960.0)
    assert config.reverse_brake_multiplier == pytest.approx(1.25)
    assert config.gravity == pytest.approx(-192.0)
    assert config.max_fall_speed is None
    assert config.scroll_speed == pytest.approx(80.0)
    assert config.platform_spacing == pytest.approx(48.0)
    assert config.easy_max_platform_shift == pytest.approx(160.0)
    assert config.minimum_horizontal_platform_shift == pytest.approx(24.0)
    assert config.generator_max_attempts == 8


def test_supported_air_release_and_reverse_controls_are_independent() -> None:
    config = _candidate_config(scroll_speed=0.0, platform_width=240.0)
    supported = ShaftEnv(config=config)
    airborne = ShaftEnv(config=config)
    try:
        supported.reset(seed=902000)
        _stand_on_first(supported)
        supported.step(int(Action.RIGHT))
        assert supported.simulator.player.body.velocity.x == pytest.approx(56.0)

        airborne.reset(seed=902000)
        body = airborne.simulator.player.body
        airborne.simulator.supported_floor = None
        body.position = (230.0, 220.0)
        body.velocity = (0.0, 0.0)
        airborne.step(int(Action.RIGHT))
        assert body.velocity.x == pytest.approx(47.6)

        _stand_on_first(supported, velocity_x=160.0)
        supported.step(int(Action.RELEASE_ALL))
        assert supported.simulator.player.body.velocity.x == pytest.approx(64.0)

        _stand_on_first(supported, velocity_x=config.max_horizontal_speed)
        supported.step(int(Action.LEFT))
        assert supported.simulator.player.body.velocity.x == pytest.approx(160.0)
    finally:
        supported.close()
        airborne.close()


def test_swept_diagonal_edge_contact_does_not_tunnel() -> None:
    diagnostic = collision_diagnostics(_candidate_config())
    assert not diagnostic["downward_tunneling_detected"]
    assert not diagnostic["diagonal_edge_tunneling_detected"]
    assert not diagnostic["moving_platform_missed"]
    assert not diagnostic["rising_from_below_landed"]
    edge = diagnostic["cases"]["diagonal_edge"]
    assert edge["landed"]
    assert edge["after"]["diagnostic"]["decision"] == "landed"
    assert 0.0 <= edge["after"]["diagnostic"]["time_of_impact"] <= 1.0


def test_render_fps_does_not_change_fixed_physics_collision() -> None:
    result = fps_invariance(_candidate_config())
    assert result["passed"]
    assert {
        item["physics_steps"] for item in result["results"].values()
    } == {72}
    assert {
        tuple(item["landing_steps"])
        for item in result["results"].values()
    } == {(1,)}


def test_scroll_distance_and_supported_player_follow_are_fixed_rate() -> None:
    config = _candidate_config()
    env = ShaftEnv(config=config)
    try:
        env.reset(seed=902001)
        simulator = env.simulator
        assert simulator is not None
        platform = min(simulator.platforms, key=lambda item: item.floor_index)
        start_platform_y = float(platform.center_y)
        start_player_y = float(simulator.player.body.position.y)
        for _ in range(config.fps):
            _observation, _reward, terminated, truncated, _info = env.step(
                int(Action.RELEASE_ALL)
            )
            assert not terminated
            assert not truncated
        assert platform.center_y - start_platform_y == pytest.approx(80.0)
        assert simulator.player.body.position.y - start_player_y == pytest.approx(80.0)
        assert simulator.supported_floor == platform.floor_index
    finally:
        env.close()


def test_generator_uses_bounded_rejection_and_reduces_clustered_layouts() -> None:
    config = _candidate_config()
    first_rng = np.random.default_rng(902002)
    second_rng = np.random.default_rng(902002)
    first = next_platform_center_with_diagnostics(config, first_rng, 231.5)
    second = next_platform_center_with_diagnostics(config, second_rng, 231.5)
    assert first == second
    assert first.attempts <= config.generator_max_attempts
    assert first.rejections < first.attempts
    assert abs(first.center_x - 231.5) >= config.minimum_horizontal_platform_shift

    distribution = layout_distribution(config, seed_count=100)
    shifts = distribution["absolute_horizontal_center_shift"]
    assert shifts["median"] >= 60.0
    assert shifts["q75"] >= 90.0
    assert distribution["trivial_transition_count_shift_below_12"] == 0
    assert distribution["impossible_transition_count_conservative"] == 0
    assert distribution["reproducible"]


def test_generator_profile_does_not_enable_special_platform_distribution() -> None:
    config = _candidate_config()
    env = ShaftEnv(config=config)
    try:
        env.reset(seed=902003)
        assert {item.kind for item in env.simulator.platforms} == {"normal"}
        assert not config.enable_spikes
        assert not config.enable_spring
        assert not config.enable_conveyor
        assert not config.enable_flipping
    finally:
        env.close()


def test_generator_duplicate_replay_is_exact() -> None:
    config = _candidate_config()
    first = ShaftEnv(config=config)
    second = ShaftEnv(config=replace(config))
    try:
        first.reset(seed=902004)
        second.reset(seed=902004)
        first_layout = [
            (item.floor_index, item.center_x, item.center_y, item.kind)
            for item in first.simulator.platforms
        ]
        second_layout = [
            (item.floor_index, item.center_x, item.center_y, item.kind)
            for item in second.simulator.platforms
        ]
        assert first_layout == second_layout
    finally:
        first.close()
        second.close()
