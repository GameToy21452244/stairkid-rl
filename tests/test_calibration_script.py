from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from stair_agent.input_controller import Action


def load_script():
    path = Path(__file__).parents[1] / "scripts" / "calibrate_dynamics.py"
    spec = importlib.util.spec_from_file_location("calibrate_dynamics", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_momentum_release_stays_bounded_and_maximizes_identifiable_releases():
    actions = load_script().action_sequence("momentum-release")

    assert len(actions) == 52
    assert actions[:4] == [Action.RELEASE_ALL] * 4
    assert actions.count(Action.RELEASE_ALL) == 28
    for index in range(4, len(actions), 8):
        assert actions[index : index + 8] == [
            Action.LEFT,
            Action.LEFT,
            Action.RELEASE_ALL,
            Action.RELEASE_ALL,
            Action.RIGHT,
            Action.RIGHT,
            Action.RELEASE_ALL,
            Action.RELEASE_ALL,
        ]


def test_reverse_braking_sequence_is_balanced_and_bounded_to_20_seconds():
    actions = load_script().action_sequence("reverse-braking")

    assert len(actions) == 156
    assert actions[:4] == [Action.RELEASE_ALL] * 4
    assert actions.count(Action.LEFT) == 76
    assert actions.count(Action.RIGHT) == 76
    for index in range(4, len(actions), 4):
        assert actions[index : index + 4] == [
            Action.RIGHT,
            Action.RIGHT,
            Action.LEFT,
            Action.LEFT,
        ]


def test_reverse_braking_boundary_guard_releases_missing_and_pushes_inward():
    bounded = load_script().bounded_reverse_action

    assert bounded(Action.LEFT, player_x=None) == Action.RELEASE_ALL
    assert bounded(Action.LEFT, player_x=70.0) == Action.RIGHT
    assert bounded(Action.RIGHT, player_x=393.0) == Action.LEFT
    assert bounded(Action.RIGHT, player_x=70.0) == Action.RIGHT
    assert bounded(Action.LEFT, player_x=393.0) == Action.LEFT
    assert bounded(Action.LEFT, player_x=200.0) == Action.LEFT
