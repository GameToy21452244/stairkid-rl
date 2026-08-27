"""Unified simulator-only training architecture for retained targets."""

from .configs import TARGET_IDS, TrainingTarget, load_training_target
from .trainer import TrainingRequest, run_training

__all__ = [
    "TARGET_IDS",
    "TrainingRequest",
    "TrainingTarget",
    "load_training_target",
    "run_training",
]
