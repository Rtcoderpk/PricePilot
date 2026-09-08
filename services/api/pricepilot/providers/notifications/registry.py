"""Notification provider registry.

`PRICEPILOT_NOTIFICATION_PROVIDER` may be `email` (needs `SMTP_*` config); empty
→ honest no-op (in-app alerts still persist, delivery is "unavailable").
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.notifications import NoopNotificationProvider, NotificationProvider

log = get_logger("providers.notifications.registry")


def build_notification_provider() -> NotificationProvider:
    names = [
        n.strip().lower()
        for n in (settings.pricepilot_notification_provider or "").split(",")
        if n.strip()
    ]
    if "email" in names:
        from pricepilot.providers.notifications.email import EmailNotificationProvider

        return EmailNotificationProvider()
    if names:
        log.warning("notification provider %r unknown; using honest no-op", names)
    return NoopNotificationProvider()