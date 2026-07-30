from __future__ import annotations

import numpy as np

from stair_agent.calibration_model import (
    CalibratedObservationModel,
    PredictedPlayer,
    ScreenPlatform,
)


def model() -> CalibratedObservationModel:
    return CalibratedObservationModel(
        vx_coefficients={
            0: np.array([0.0, 0.0]),
            1: np.array([1.0, -10.0]),
            2: np.array([1.0, 10.0]),
        },
        vy_coefficients={
            -1: np.array([1.0, 10.0]),
            1: np.array([1.0, 10.0]),
        },
        dx_coefficients={
            action: np.array([0.0, 1.0, 0.0]) for action in (0, 1, 2)
        },
        dy_coefficients={
            motion: np.array([0.0, 1.0, 0.0]) for motion in (-1, 1)
        },
        scroll_velocity_y=0.0,
        normal_bounce_velocity_y=-90.0,
        spring_bounce_velocity_y=-180.0,
        normal_rising_duration_steps=3,
        spring_rising_duration_steps=5,
        apex_velocity_y=50.0,
        apex_delta_y=6.0,
        screen_gravity_y=100.0,
    )


def test_model_switches_from_rising_to_falling_at_apex():
    player = PredictedPlayer(100, 100, 0, -5, -1, phase_steps=2)

    landed = model().step(player, [], action=0, dt=0.1)

    assert not landed
    assert player.motion == 1
    assert player.vy == 5


def test_model_predicts_normal_platform_landing():
    player = PredictedPlayer(100, 100, 0, 20, 1)
    platforms = [ScreenPlatform(100, 116, 96, 0.0)]

    landed = model().step(player, platforms, action=0, dt=0.1)

    assert landed
    assert player.motion == -1
    assert player.vy == -90


def test_model_sweeps_moving_platform_from_old_to_new_top():
    calibrated = model()
    object.__setattr__(calibrated, "scroll_velocity_y", -90.0)
    player = PredictedPlayer(100, 100, 0, 20, 1)
    platforms = [ScreenPlatform(100, 116, 96, 0.0)]

    landed = calibrated.step(player, platforms, action=0, dt=0.1)

    assert landed
