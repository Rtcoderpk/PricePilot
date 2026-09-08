"""Test configuration: isolated settings defaults."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("PRICEPILOT_ENABLE_FIXTURES", "false")
os.environ.setdefault("AI_PROVIDER", "")
os.environ.setdefault("AI_API_KEY", "")