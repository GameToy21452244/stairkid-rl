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
