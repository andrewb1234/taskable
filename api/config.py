"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default SQLite location: a hidden folder in the user's home directory so the
# DB survives `git clean`, is trivial to back up / inspect with desktop tools,
# and stays consistent across bare-metal and docker-bind-mount deployments.
# Override with the DATABASE_URL env var when you need something else (eg.
# `:memory:` in tests, a Postgres URL in production).
_DEFAULT_DB_DIR = Path.home() / ".taskable"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "taskable.db"
_DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DB_PATH}"


class Settings(BaseSettings):
    """Typed, cached runtime settings for the FastAPI process."""

    github_pat: str | None = None
    database_url: str = _DEFAULT_DATABASE_URL
    migration_mode: Literal["upgrade", "check"] = "upgrade"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Auth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    local_auth_enabled: bool = False
    jwt_secret: str = "dev-jwt-secret-change-me"
    frontend_url: str = "http://localhost:5173"
    auth_rate_limit: int = 10
    auth_rate_window_seconds: int = 300
    action_rate_limit: int = 180
    action_rate_window_seconds: int = 60
    # Required to adopt pre-tenancy projects in a production database. Local
    # development may safely adopt them when exactly one user exists.
    legacy_owner_email: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def is_production(self) -> bool:
        """Return whether trusted configuration describes an HTTPS deployment."""
        return self.frontend_url.startswith("https://")

    def public_origin(self) -> str:
        """Return the configured frontend origin without a path or query."""
        parsed = urlsplit(self.frontend_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("FRONTEND_URL must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password:
            raise RuntimeError("FRONTEND_URL must not contain credentials.")
        return f"{parsed.scheme}://{parsed.netloc}"

    def validate_production(self) -> None:
        """Raise if security-sensitive defaults are still set in production."""
        parsed = urlsplit(self.public_origin())
        rate_values = {
            "AUTH_RATE_LIMIT": self.auth_rate_limit,
            "AUTH_RATE_WINDOW_SECONDS": self.auth_rate_window_seconds,
            "ACTION_RATE_LIMIT": self.action_rate_limit,
            "ACTION_RATE_WINDOW_SECONDS": self.action_rate_window_seconds,
        }
        invalid_rate_values = [
            name for name, value in rate_values.items() if value <= 0
        ]
        if invalid_rate_values:
            raise RuntimeError(
                "Rate-limit settings must be positive: "
                + ", ".join(invalid_rate_values)
            )
        if self.local_auth_enabled and parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise RuntimeError(
                "LOCAL_AUTH_ENABLED is restricted to loopback FRONTEND_URL "
                "origins. Use a configured identity provider for hosted use."
            )
        if not self.is_production():
            return
        if self.local_auth_enabled:
            raise RuntimeError(
                "LOCAL_AUTH_ENABLED must be false in production."
            )
        if (
            self.jwt_secret == "dev-jwt-secret-change-me"
            or len(self.jwt_secret) < 32
        ):
            raise RuntimeError(
                "JWT_SECRET must contain at least 32 characters and must not "
                "use the development default in production."
            )
        if not self.google_client_id or not self.google_client_secret:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured "
                "in production."
            )
        if self.migration_mode != "check":
            raise RuntimeError(
                "MIGRATION_MODE must be 'check' in production. Run a single "
                "`python -m api.migrations upgrade --backup-confirmed` job "
                "before starting application instances."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
