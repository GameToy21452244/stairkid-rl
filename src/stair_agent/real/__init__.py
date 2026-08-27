"""Fail-closed Real-game runtime composition.

Importing this package never opens a window, starts capture, or constructs an
input controller.  Those side effects are restricted to the explicitly
authorized live entry point.
"""

from .runtime import RealDryRunResult, RealRunResult, prepare_real_dry_run, run_live_real

__all__ = [
    "RealDryRunResult",
    "RealRunResult",
    "prepare_real_dry_run",
    "run_live_real",
]
