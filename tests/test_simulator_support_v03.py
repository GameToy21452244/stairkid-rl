from __future__ import annotations

import pytest

from stair_agent.envs.shaft_env import ShaftEnv
from stair_agent.input_controller import Action
from stair_agent.policies.simulator_teachers import OracleFull
from stair_agent.simulator.state import ShaftEnvConfig


def test_calibrated_playfield_matches_real_capture_bounds() -> None:
    env = ShaftEnv(config=ShaftEnvConfig())
    try:
        env.reset(seed=10006)
        assert env.simulator.player.body.position.x == pytest.approx(231.5)
        assert (
            env.config.height - env.simulator.player.body.position.y
        ) == pytest.approx(338.5)
        assert all(
            platform.left >= env.config.playfield_left - 1e-6
            and platform.right <= env.config.playfield_right + 1e-6
            for platform in env.simulator.platforms
        )
    finally:
        env.close()


def test_release_cannot_descend_through_initial_scrolling_platform() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(max_episode_steps=100))
    try:
        env.reset(seed=10007)
        source = env.simulator.platforms[0]
        initial_offset = (
            env.simulator.player.body.position.y
            - source.top
        )

        for _ in range(8):
            _, _, terminated, truncated, info = env.step(
                int(Action.RELEASE_ALL)
            )
            assert not terminated
            assert not truncated
            assert "floor_descended" not in info["events"]
            assert env.simulator.deepest_floor == 0
            assert env.simulator.supported_floor == source.floor_index
            assert (
                env.simulator.player.body.position.y - source.top
            ) == pytest.approx(initial_offset)
    finally:
        env.close()


def test_support_departure_requires_clearing_platform_edge() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(max_episode_steps=100))
    try:
        env.reset(seed=10008)
        source = env.simulator.platforms[0]
        departure_seen = False

        for _ in range(12):
            _, _, terminated, truncated, info = env.step(int(Action.LEFT))
            assert not terminated
            assert not truncated
            player_right = (
                float(env.simulator.player.body.position.x)
                + env.simulator.player.width / 2
            )
            if "support_departed" in info["events"]:
                departure_seen = True
                assert player_right <= source.left + 1e-6
                assert env.simulator.supported_floor is None
                break
            assert player_right > source.left
            assert env.simulator.supported_floor == source.floor_index
            assert env.simulator.deepest_floor == 0

        assert departure_seen
    finally:
        env.close()


def test_scrolling_support_carries_player_at_platform_velocity() -> None:
    config = ShaftEnvConfig(scroll_speed=96.0)
    env = ShaftEnv(config=config)
    try:
        env.reset(seed=10009)
        source = env.simulator.platforms[0]
        initial_player_y = float(env.simulator.player.body.position.y)
        initial_platform_y = source.center_y

        env.step(int(Action.RELEASE_ALL))

        player_shift = (
            float(env.simulator.player.body.position.y) - initial_player_y
        )
        platform_shift = source.center_y - initial_platform_y
        assert player_shift == pytest.approx(platform_shift)
        assert env.simulator.player.body.velocity.y == pytest.approx(
            config.scroll_speed
        )
    finally:
        env.close()


def test_oracle_descends_by_edge_departure_before_each_new_floor() -> None:
    env = ShaftEnv(
        config=ShaftEnvConfig(
            distribution="easy",
            max_episode_steps=300,
        )
    )
    oracle = OracleFull()
    try:
        env.reset(seed=10010)
        departed_sources: set[int] = set()
        for _ in range(300):
            previous_deepest = env.simulator.deepest_floor
            previous_support = env.simulator.supported_floor
            decision = oracle.choose(env.simulator)
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            if "support_departed" in info["events"]:
                assert previous_support is not None
                departed_sources.add(previous_support)
            if env.simulator.deepest_floor > previous_deepest:
                assert previous_deepest in departed_sources
            if env.simulator.deepest_floor >= 3:
                break
            assert not terminated
            assert not truncated

        assert env.simulator.deepest_floor >= 3
    finally:
        env.close()


def test_oracle_uses_one_extra_floor_under_top_pressure() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    oracle = OracleFull(
        top_pressure_screen_y=120.0,
        top_pressure_lookahead=2,
    )
    try:
        env.reset(seed=10011)
        ordinary = oracle.choose(env.simulator)
        assert ordinary.target_platform_id == 1

        env.simulator.player.body.position = (
            env.simulator.player.body.position.x,
            env.simulator.config.height - 110.0,
        )
        source = env.simulator.platforms[0]
        source.body.position = (
            source.body.position.x,
            env.simulator.player.body.position.y
            - env.simulator.player.height / 2
            - source.height / 2,
        )
        pressured = oracle.choose(env.simulator)

        assert pressured.target_platform_id == 2
    finally:
        env.close()


def test_oracle_keeps_departure_direction_when_top_pressure_retargets() -> None:
    env = ShaftEnv(config=ShaftEnvConfig(distribution="easy"))
    oracle = OracleFull()
    saw_retarget_while_supported = False
    try:
        env.reset(seed=13009)
        for _ in range(80):
            support = env.simulator.supported_floor
            decision = oracle.choose(env.simulator)
            if support == 5 and decision.target_platform_id == 8:
                saw_retarget_while_supported = True
                assert decision.action is Action.RIGHT
            _, _, terminated, truncated, info = env.step(
                int(decision.action)
            )
            if saw_retarget_while_supported:
                assert "support_departed" in info["events"]
                break
            assert not terminated
            assert not truncated

        assert saw_retarget_while_supported
    finally:
        env.close()
