"""Email notification provider (SMTP-gated).

Requires SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD + a sender. When any is
missing `available()` is False and `deliver` returns an honest
"unavailable" result — never pretends an email was sent.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.notifications import NotificationDelivery, NotificationProvider

log = get_logger("providers.notifications.email")


class EmailNotificationProvider(NotificationProvider):
    name = "email"

    def __init__(self) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.sender = settings.smtp_sender

    async def available(self) -> bool:
        return bool(self.host and self.username and self.password and self.sender)

    async def deliver(self, *, user_id: str, title: str, body: str) -> NotificationDelivery:
        if not await self.available():
            return NotificationDelivery("email", "unavailable", reason="SMTP not configured")
        # SMTP send is intentionally a synchronous/async stubbed boundary: a real
        # SMTP library call would go here. We never claim success without sending.
        return NotificationDelivery("email", "unavailable", reason="Email delivery not implemented in this environment")