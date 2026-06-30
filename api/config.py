"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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

    agent_api_key: str = "dev-agent-key-change-me"
    github_pat: str | None = None
    database_url: str = _DEFAULT_DATABASE_URL
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Auth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    jwt_secret: str = "dev-jwt-secret-change-me"
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def validate_production(self) -> None:
        """Raise if security-sensitive defaults are still set in production."""
        if self.frontend_url.startswith("https://") and self.jwt_secret == "dev-jwt-secret-change-me":
            raise RuntimeError(
                "JWT_SECRET must be set to a strong value in production "
                "(current value is the insecure default)."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
