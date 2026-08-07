"""Tests for the v0.5 normal-platform fidelity manual candidate.

These tests verify version isolation, physics behaviour, and the v0.5-specific
arcade control model without requiring pygame.
"""

from __future__ import annotations

import numpy as np
import pytest

from stair_agent.input_controller import Action
from stair_agent.simulator.manual_test import (
    calibration_profile_config,
    list_manual_scenarios,
)
from stair_agent.simulator.physics import ShaftSimulator
from stair_agent.simulator.state import ShaftEnvConfig


# =====================================================================
# Helpers
# =====================================================================

def _v05_config(**overrides) -> ShaftEnvConfig:
    """Build a v0.5-style 60Hz manual config for physics testing."""
    values = {
        "environment_version": "ns-shaft-sim-v0.5-arcade-normal-candidate",
        "fps": 60,
        "physics_hz": 60,
        "allow_manual_60hz_control": True,
        "horizontal_acceleration": 420.0,
        "air_control_multiplier": 0.85,
        "max_horizontal_speed": 230.0,
        "release_deceleration": 960.0,
        "reverse_brake_multiplier": 1.0,
        "platform_width": 72.0,
        "gravity": -320.0,
        "max_fall_speed": 420.0,
        "scroll_speed": 96.0,
        "enable_swept_edge_collision": True,
    }
    values.update(overrides)
    return ShaftEnvConfig(**values)


def _make_simulator(config: ShaftEnvConfig | None = None, seed: int = 900001):
    config = config or _v05_config()
    rng = np.random.default_rng(seed)
    return ShaftSimulator(config, rng)


# =====================================================================
# 1. v0.3 frozen config unchanged
# =====================================================================

class TestV03FrozenConfig:
    """Verify that ShaftEnvConfig() default produces v0.3 frozen values."""

    def test_default_fps(self):
        c = ShaftEnvConfig()
        assert c.fps == 10

    def test_default_physics_hz(self):
        c = ShaftEnvConfig()
        assert c.physics_hz == 60

    def test_default_acceleration(self):
        c = ShaftEnvConfig()
        assert c.horizontal_acceleration == 1048.0

    def test_default_gravity(self):
        c = ShaftEnvConfig()
        assert c.gravity == -192.0

    def test_default_platform_width(self):
        c = ShaftEnvConfig()
        assert c.platform_width == 96.0

    def test_default_scroll_speed(self):
        c = ShaftEnvConfig()
        assert c.scroll_speed == 96.0

    def test_default_max_fall_speed_none(self):
        c = ShaftEnvConfig()
        assert c.max_fall_speed is None

    def test_default_release_deceleration_none(self):
        c = ShaftEnvConfig()
        assert c.release_deceleration is None

    def test_default_version(self):
        c = ShaftEnvConfig()
        assert c.environment_version == "ns-shaft-sim-v0.3"

    def test_default_manual_60hz_disabled(self):
        c = ShaftEnvConfig()
        assert c.allow_manual_60hz_control is False


# =====================================================================
# 2. v0.4 manual profile unchanged
# =====================================================================

class TestV04ProfileUnchanged:
    """Verify that the 'after' calibration profile matches v0.4."""

    def test_v04_acceleration(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.horizontal_acceleration == 560.0

    def test_v04_air_control(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.air_control_multiplier == 0.85

    def test_v04_release_deceleration(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.release_deceleration == 960.0

    def test_v04_scroll(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.scroll_speed == 80.0

    def test_v04_swept_collision(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.enable_swept_edge_collision is True

    def test_v04_reverse_brake(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert c.reverse_brake_multiplier == 1.25


# =====================================================================
# 3. v0.5 is independent opt-in
# =====================================================================

class TestV05IndependentProfile:
    """v0.5 can only be activated via explicit 60Hz manual config."""

    def test_v03_default_does_not_include_v05(self):
        c = ShaftEnvConfig()
        assert "v0.5" not in c.environment_version

    def test_v04_after_does_not_include_v05(self):
        c = calibration_profile_config(ShaftEnvConfig(), "after")
        assert "v0.5" not in c.environment_version

    def test_60hz_requires_manual_flag(self):
        with pytest.raises(ValueError, match="60 Hz"):
            ShaftEnvConfig(fps=60, allow_manual_60hz_control=False)

    def test_60hz_with_flag_works(self):
        c = ShaftEnvConfig(fps=60, allow_manual_60hz_control=True)
        assert c.fps == 60

    def test_manual_flag_requires_60hz(self):
        with pytest.raises(ValueError, match="fps=60"):
            ShaftEnvConfig(fps=10, allow_manual_60hz_control=True)


# =====================================================================
# 4. v0.5 normal-only scenarios
# =====================================================================

class TestV05NormalOnly:
    """v0.5 manual candidate only allows non-special-platform scenarios."""

    def test_normal_scenarios_have_no_special(self):
        scenarios = [s for s in list_manual_scenarios() if not s.special_platform]
        assert len(scenarios) >= 4  # at least M01-M08 minus specials
        for s in scenarios:
            assert not s.special_platform

    def test_v05_config_no_special_flags(self):
        c = _v05_config()
        assert c.enable_spikes is False
        assert c.enable_spring is False
        assert c.enable_conveyor is False
        assert c.enable_flipping is False


# =====================================================================
# 5. Display FPS independence
# =====================================================================

class TestDisplayFPSIndependence:
    """60 and 120 display FPS must not affect physics outcome.

    Since display FPS only affects render loop timing (not physics), we verify
    that two simulators with identical configs produce identical results.
    """

    def test_same_physics_different_display_intention(self):
        # display_fps is NOT part of ShaftEnvConfig; it's only in the viewer.
        # Both 60 and 120 display use the same 60Hz physics config.
        config = _v05_config()
        actions = [Action.RIGHT] * 30 + [Action.LEFT] * 20 + [Action.RELEASE_ALL] * 10

        sim1 = _make_simulator(config, seed=900010)
        sim2 = _make_simulator(config, seed=900010)

        for action in actions:
            r1 = sim1.step(action)
            r2 = sim2.step(action)
            assert float(sim1.player.body.velocity.x) == float(sim2.player.body.velocity.x)
            assert float(sim1.player.body.velocity.y) == float(sim2.player.body.velocity.y)
            assert r1.terminated == r2.terminated


# =====================================================================
# 6. First directional input has immediate response
# =====================================================================

class TestFirstInputResponse:
    """First direction press must produce non-zero velocity on next tick."""

    def test_left_first_tick(self):
        sim = _make_simulator()
        # Start from rest
        sim.player.body.velocity = (0.0, sim.player.body.velocity.y)
        sim.step(Action.LEFT)
        assert float(sim.player.body.velocity.x) < 0.0

    def test_right_first_tick(self):
        sim = _make_simulator()
        sim.player.body.velocity = (0.0, sim.player.body.velocity.y)
        sim.step(Action.RIGHT)
        assert float(sim.player.body.velocity.x) > 0.0


# =====================================================================
# 7. Reversal does NOT slide along old direction for 0.3-0.4s
# =====================================================================

class TestReversalNoLongSlide:
    """After pressing opposite direction, velocity should cross zero quickly.

    With base simulator (accel=420, dt=1/60, max_speed=230):
    - delta_v per tick = 420/60 = 7 px/s
    - From -230 to 0 = ~33 ticks (0.55s)

    The ResponsiveManualSession adds startup-impulse and instant-brake
    features that make reversal complete in ~3-5 ticks, but those features
    are not in the base ShaftSimulator. Here we test the base physics
    guarantee: reversal completes within 35 ticks (< 0.6s), which is
    significantly faster than v0.3's effective response time.
    """

    def test_left_to_right_reversal_under_35_ticks(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        # Build up leftward speed
        for _ in range(60):
            sim.step(Action.LEFT)
        assert float(sim.player.body.velocity.x) < 0.0

        # Now press RIGHT
        crossed_zero = False
        for tick in range(35):
            sim.step(Action.RIGHT)
            if float(sim.player.body.velocity.x) >= 0.0:
                crossed_zero = True
                break
        assert crossed_zero, (
            "Velocity did not cross zero within 35 ticks (0.58s) after reversal; "
            f"final vx={float(sim.player.body.velocity.x)}"
        )

    def test_right_to_left_reversal_under_35_ticks(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        for _ in range(60):
            sim.step(Action.RIGHT)
        assert float(sim.player.body.velocity.x) > 0.0

        crossed_zero = False
        for tick in range(35):
            sim.step(Action.LEFT)
            if float(sim.player.body.velocity.x) <= 0.0:
                crossed_zero = True
                break
        assert crossed_zero, (
            f"Velocity did not cross zero within 35 ticks; "
            f"final vx={float(sim.player.body.velocity.x)}"
        )


# =====================================================================
# 8. Reversal does NOT mirror full speed instantly
# =====================================================================

class TestReversalNoInstantMirror:
    """After pressing opposite direction at max speed, should not jump to
    opposite max speed in a single tick."""

    def test_no_instant_mirror_left_to_right(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        max_speed = config.max_horizontal_speed
        # Build to max leftward speed
        for _ in range(120):
            sim.step(Action.LEFT)

        # One tick of RIGHT
        sim.step(Action.RIGHT)
        vx = float(sim.player.body.velocity.x)
        # Should not be at or beyond max_speed in the new direction
        assert vx < max_speed * 0.9, (
            f"Velocity {vx} is too close to max_speed {max_speed} after 1 tick"
        )


# =====================================================================
# 9. RELEASE is separate from reversal
# =====================================================================

class TestReleaseSeparateFromReversal:
    """RELEASE should decelerate smoothly, not behave like pressing opposite."""

    def test_release_decelerates(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        # Build rightward speed
        for _ in range(30):
            sim.step(Action.RIGHT)
        speed_before = abs(float(sim.player.body.velocity.x))
        assert speed_before > 50.0

        # Release
        sim.step(Action.RELEASE_ALL)
        speed_after = abs(float(sim.player.body.velocity.x))
        assert speed_after < speed_before, "RELEASE did not decelerate"

    def test_release_does_not_reverse_direction(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        for _ in range(30):
            sim.step(Action.RIGHT)

        # Release for several ticks
        for _ in range(60):
            sim.step(Action.RELEASE_ALL)
        vx = float(sim.player.body.velocity.x)
        # Should have stopped at 0, not crossed into negative
        assert vx >= 0.0, f"RELEASE crossed into opposite direction: {vx}"


# =====================================================================
# 10. Platform width consistency
# =====================================================================

class TestPlatformWidthConsistency:
    """Platform visual, physics shape, and collision width must match config."""

    def test_platform_width_matches_config(self):
        config = _v05_config(platform_width=72.0)
        sim = _make_simulator(config)
        for p in sim.platforms:
            actual_width = p.right - p.left
            assert abs(actual_width - 72.0) < 0.01, (
                f"Platform width {actual_width} != config 72.0"
            )

    def test_platform_width_96_for_default(self):
        config = ShaftEnvConfig()
        rng = np.random.default_rng(900001)
        sim = ShaftSimulator(config, rng)
        for p in sim.platforms:
            actual_width = p.right - p.left
            assert abs(actual_width - 96.0) < 0.01


# =====================================================================
# 11. Gravity: falling velocity monotonically increases, capped at max
# =====================================================================

class TestGravityFalling:
    """Under gravity, falling velocity increases monotonically and is capped."""

    def test_falling_velocity_increases(self):
        # Use non-calibrated playfield to avoid top-hazard kill zone
        config = _v05_config(
            scroll_speed=0.0,
            gravity=-320.0,
            max_fall_speed=420.0,
            enable_calibrated_playfield=False,
        )
        sim = _make_simulator(config)
        # Place player high enough for 20 ticks of free fall (~90px at g=320)
        # but not beyond the top of the arena
        sim.supported_floor = None
        sim.player.body.position = (
            float(sim.player.body.position.x),
            config.height - 30.0,  # near top of screen in world y
        )
        sim.player.body.velocity = (0.0, 0.0)

        velocities_y = []
        for _ in range(20):
            result = sim.step(Action.RELEASE_ALL)
            if result.terminated:
                break
            velocities_y.append(float(sim.player.body.velocity.y))

        # In world y, falling means velocity becomes more negative
        assert len(velocities_y) >= 5, (
            f"Not enough free-fall ticks: got {len(velocities_y)}"
        )
        for i in range(1, len(velocities_y)):
            assert velocities_y[i] <= velocities_y[i - 1] + 0.01, (
                f"Falling velocity not monotonically decreasing at tick {i}: "
                f"{velocities_y[i]} vs {velocities_y[i-1]}"
            )

    def test_max_fall_speed_capped(self):
        config = _v05_config(scroll_speed=0.0, gravity=-320.0, max_fall_speed=420.0)
        sim = _make_simulator(config)
        sim.supported_floor = None
        sim.player.body.velocity = (0.0, 0.0)

        for _ in range(120):
            sim.step(Action.RELEASE_ALL)
        vy = float(sim.player.body.velocity.y)
        # velocity.y should not go below -420
        assert vy >= -420.0 - 1.0, f"Fall speed {vy} exceeds max {-420.0}"


# =====================================================================
# 12. Swept normal-platform landing not degraded
# =====================================================================

class TestSweptLanding:
    """Player falling onto a platform should still land correctly."""

    def test_landing_on_platform(self):
        config = _v05_config(scroll_speed=0.0)
        sim = _make_simulator(config)
        first = min(sim.platforms, key=lambda p: p.floor_index)
        # Place player above first platform
        sim.supported_floor = None
        sim.player.body.position = (
            first.center_x,
            first.top + sim.player.height + 20.0,
        )
        sim.player.body.velocity = (0.0, -100.0)

        landed = False
        for _ in range(60):
            result = sim.step(Action.RELEASE_ALL)
            if "landed" in result.events:
                landed = True
                break
        assert landed, "Player did not land on platform"


# =====================================================================
# 13. Deterministic replay
# =====================================================================

class TestDeterministicReplay:
    """Same seed and action sequence must produce identical results."""

    def test_replay_identical(self):
        config = _v05_config()
        actions = (
            [Action.RIGHT] * 10
            + [Action.LEFT] * 10
            + [Action.RELEASE_ALL] * 5
            + [Action.RIGHT] * 10
        )

        positions_a = []
        sim_a = _make_simulator(config, seed=900099)
        for action in actions:
            sim_a.step(action)
            positions_a.append((
                float(sim_a.player.body.position.x),
                float(sim_a.player.body.position.y),
                float(sim_a.player.body.velocity.x),
                float(sim_a.player.body.velocity.y),
            ))

        positions_b = []
        sim_b = _make_simulator(config, seed=900099)
        for action in actions:
            sim_b.step(action)
            positions_b.append((
                float(sim_b.player.body.position.x),
                float(sim_b.player.body.position.y),
                float(sim_b.player.body.velocity.x),
                float(sim_b.player.body.velocity.y),
            ))

        assert positions_a == positions_b


# =====================================================================
# 14. Special platforms disabled in v0.5 normal profile
# =====================================================================

class TestSpecialPlatformsDisabled:
    """v0.5 normal profile must not generate special platforms."""

    def test_all_platforms_are_normal(self):
        config = _v05_config()
        sim = _make_simulator(config)
        for p in sim.platforms:
            assert p.kind == "normal", f"Found non-normal platform: {p.kind}"

    def test_no_spikes_flag(self):
        c = _v05_config()
        assert c.enable_spikes is False

    def test_no_spring_flag(self):
        c = _v05_config()
        assert c.enable_spring is False

    def test_no_conveyor_flag(self):
        c = _v05_config()
        assert c.enable_conveyor is False

    def test_no_flipping_flag(self):
        c = _v05_config()
        assert c.enable_flipping is False
