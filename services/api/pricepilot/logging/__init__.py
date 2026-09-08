"""Structured JSON logging with request-id context.

Log format is single-line JSON so it can be parsed by log aggregators.
Every log line carries the current request_id when one is set on the context
variable (see api/middleware.py). Secrets never reach the logger.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar

from pricepilot.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        return json.dumps(payload, ensure_ascii=False, default=str)


def _configure() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("pricepilot")
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    root.propagate = False


_configure()


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under `pricepilot`.

    Explicitly force-disables propagation on the returned logger too, because a
    bare child logger of a non-propagating root would otherwise emit nothing.
    """
    log = logging.getLogger(f"pricepilot.{name}")
    log.setLevel(settings.log_level.upper())
    log.propagate = False
    return log