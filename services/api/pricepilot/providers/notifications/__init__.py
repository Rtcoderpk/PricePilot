"""Notification provider contract for price alerts.

In-app notifications are always persisted. An optional Email/Webhook provider
can deliver externally; when one is not configured, `deliver` returns an honest
`NotificationDelivery(status="unavailable")` — we never pretend an email was sent.
A delivery failure must never destroy the alert/observation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationDelivery:
    channel: str
    status: str  # "delivered" | "unavailable" | "failed"
    reason: str | None = None


class NotificationProvider(ABC):
    name: str = "notifications"

    @abstractmethod
    async def available(self) -> bool:
        """Whether this delivery channel is configured."""

    @abstractmethod
    async def deliver(self, *, user_id: str, title: str, body: str) -> NotificationDelivery:
        """Deliver a notification; returns the honest delivery result."""


class NoopNotificationProvider(NotificationProvider):
    """Honest no-op: delivery is unavailable, never faked."""

    name = "notifications_unavailable"

    async def available(self) -> bool:
        return False

    async def deliver(self, *, user_id: str, title: str, body: str) -> NotificationDelivery:
        return NotificationDelivery(channel="in_app", status="unavailable", reason="No notification provider configured")