"""Production config guard (Phase 7).

Fails fast when the app is started in `production` with a placeholder secret,
so a misconfigured deployment cannot silently run with a known default value.
"""

from __future__ import annotations

PLACEHOLDER_JWT_SECRET = "change-me-in-prod"


def placeholder_jwt_secret_allowed(secret: str, *, app_env: str) -> bool:
    """True when the secret is usable in this environment.

    In production the known placeholder is refused; elsewhere (dev/test) it is
    allowed so local bring-up keeps working.
    """
    return not (
        app_env == "production" and secret.strip().lower() == PLACEHOLDER_JWT_SECRET.lower()
    )


def assert_production_config_safe(*, app_env: str, jwt_secret: str) -> None:
    """Raise a RuntimeError when production config is unsafe."""
    if not placeholder_jwt_secret_allowed(jwt_secret, app_env=app_env):
        raise RuntimeError(
            "Refusing to start in production with the placeholder JWT secret. "
            "Set JWT_SECRET to a strong secret before deploying."
        )