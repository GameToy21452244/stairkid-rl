"""Deployable route intent using only structured screen observations."""

from __future__ import annotations

from ..baseline_policy import SafePlatformPolicy
from ..config import BaselineConfig


OBSERVABLE_ROUTE_INTENT_POLICY_VERSION = (
    "teacher-observable-v5-support-extent-route-intent"
)


class ObservableRouteIntentPolicy(SafePlatformPolicy):
    """Keep source-to-destination intent until observable AABB separation."""

    policy_version = OBSERVABLE_ROUTE_INTENT_POLICY_VERSION

    def __init__(self, config: BaselineConfig | None = None) -> None:
        super().__init__(
            config or BaselineConfig(),
            support_contact_uses_tracker_aabb_overlap=True,
        )


__all__ = [
    "OBSERVABLE_ROUTE_INTENT_POLICY_VERSION",
    "ObservableRouteIntentPolicy",
]
