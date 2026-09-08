"""Structured error taxonomy shared by the API and the provider stack.

All user-facing errors are returned through a single JSON envelope:
{ "error": { "code", "message", "details?" } }
HTTP status codes are mapped at the API layer (errors.py → api handlers).
Internal stack traces and secrets are never exposed to clients.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    BAD_GATEWAY = "bad_gateway"
    INTERNAL_ERROR = "internal_error"
    DATABASE_ERROR = "database_error"
    CONFLICT = "conflict"


class PricePilotError(Exception):
    """Base error with a stable machine-readable code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code or _default_status(code)
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code.value, "message": self.message}


class ProviderUnavailableError(PricePilotError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(
            ErrorCode.PROVIDER_UNAVAILABLE,
            message=f"{provider}: {message}",
            status_code=503,
        )
        self.provider = provider


class ProviderError(PricePilotError):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status_code: int = 502,
        details: Any = None,
    ) -> None:
        super().__init__(
            ErrorCode.PROVIDER_ERROR,
            message=f"{provider}: {message}",
            status_code=status_code,
            details=details,
        )
        self.provider = provider


def _default_status(code: ErrorCode) -> int:
    return {
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.UNAUTHORIZED: 401,
        ErrorCode.FORBIDDEN: 403,
        ErrorCode.RATE_LIMITED: 429,
        ErrorCode.PROVIDER_UNAVAILABLE: 503,
        ErrorCode.PROVIDER_ERROR: 502,
        ErrorCode.UPSTREAM_TIMEOUT: 504,
        ErrorCode.BAD_GATEWAY: 502,
        ErrorCode.INTERNAL_ERROR: 500,
        ErrorCode.DATABASE_ERROR: 500,
        ErrorCode.CONFLICT: 409,
    }.get(code, 500)