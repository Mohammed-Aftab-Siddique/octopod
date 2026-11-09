"""Application settings.

Settings are built from the Worker ``env`` object on the first request. Reading
environment variables (or ``.env`` files) at import time is deliberately avoided:
a Python Worker receives its vars and secrets through ``request.scope["env"]``.

For local development and the pytest suite the same values can be supplied through
``os.environ``; that path is only used when no Worker env is available.
"""

import os
from pathlib import Path

from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    app_name: str = "Octopod Roster"
    environment: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'octopod.db'}"
    secret_key: str = "dev-secret-change-me"
    session_cookie_name: str = "octopod_session"
    session_ttl_hours: int = 168
    cookie_secure: bool = False
    auto_create_tables: bool = False
    seed_demo: bool = False
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


_settings: Settings | None = None


def _lookup(env, name: str, default: str) -> str:
    value = None
    if env is not None:
        if isinstance(env, dict):
            value = env.get(name)
        else:
            value = getattr(env, name, None)
    if value is None or value == "":
        value = os.environ.get(name)
    if value is None:
        return default
    return str(value)


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def settings_from_env(env=None) -> Settings:
    """Build settings from a Worker ``env`` object or the local environment."""

    return Settings(
        environment=_lookup(env, "ENVIRONMENT", "development"),
        database_url=_lookup(env, "DATABASE_URL", f"sqlite:///{BASE_DIR / 'octopod.db'}"),
        secret_key=_lookup(env, "SECRET_KEY", "dev-secret-change-me"),
        session_cookie_name=_lookup(env, "SESSION_COOKIE_NAME", "octopod_session"),
        session_ttl_hours=_as_int(_lookup(env, "SESSION_TTL_HOURS", "168"), 168),
        cookie_secure=_as_bool(_lookup(env, "COOKIE_SECURE", "false")),
        auto_create_tables=_as_bool(_lookup(env, "AUTO_CREATE_TABLES", "false")),
        seed_demo=_as_bool(_lookup(env, "SEED_DEMO", "false")),
        allowed_origins=_lookup(
            env,
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ),
    )


def get_settings(env=None) -> Settings:
    """Return the cached settings for this isolate.

    Always pass the request's ``env`` on the first call. The cache is reset by
    tests, which is also the only supported way to switch environments in a
    running process.
    """

    global _settings
    if _settings is None:
        _settings = settings_from_env(env)
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
