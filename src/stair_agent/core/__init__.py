"""Stable shared runtime primitives for simulator and Real inference."""

from .contracts import ActionTiming, OBSERVATION_DIM, OBSERVATION_SCHEMA_VERSION
from .model_registry import (
    CanonicalModel,
    LoadedCanonicalModel,
    ModelRegistryError,
    load_canonical_model,
    load_model_registry,
)

__all__ = [
    "ActionTiming",
    "CanonicalModel",
    "LoadedCanonicalModel",
    "ModelRegistryError",
    "OBSERVATION_DIM",
    "OBSERVATION_SCHEMA_VERSION",
    "load_canonical_model",
    "load_model_registry",
]
