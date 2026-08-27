from __future__ import annotations

from enum import IntEnum


class Action(IntEnum):
    """Shared policy action identity, independent of any input backend."""

    RELEASE_ALL = 0
    LEFT = 1
    RIGHT = 2
