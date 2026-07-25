"""Provision an authenticated single-user local Mouvadah installation.

This command is intentionally unavailable for hosted/HTTPS deployments. It
creates (or reuses) a local owner, ensures the personal workspace exists, and
issues a revocable database-backed API key for browser bootstrap and MCP use.
The full key is written atomically to a user-owned ``0600`` credentials file;
it is never stored by the API in plaintext.

Run after setting ``LOCAL_AUTH_ENABLED=true``::

    python -m api.local_setup --email owner@example.com --name "Local Owner"
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from api.api_keys import hash_api_key, issue_api_key
from api.authorization import ensure_personal_workspace
from api.config import Settings, get_settings
from api.database import engine, init_db
from api.models.entities import ApiKey, User
from api.utils.time import utcnow

DEFAULT_CREDENTIALS_FILE = (
    Path.home() / ".config" / "mouvadah" / "credentials.env"
)
LOCAL_KEY_NAME = "Local MCP bootstrap"
LOCAL_KEY_EXPIRY_DAYS = 365


@dataclass(frozen=True)
class LocalSetupResult:
    user: User
    api_key: ApiKey
    raw_key: str
    reused_key: bool


def _validate_identity(email: str, name: str) -> tuple[str, str]:
    clean_email = email.strip().lower()
    clean_name = name.strip()
    if (
        "@" not in clean_email
        or any(char.isspace() for char in clean_email)
        or clean_email.startswith("@")
        or clean_email.endswith("@")
    ):
        raise ValueError("A valid local owner email is required.")
    if not clean_name:
        raise ValueError("A non-empty local owner name is required.")
    return clean_email, clean_name


def _active_key_for_user(
    session: Session,
    *,
    raw_key: str,
    user_id: int,
) -> ApiKey | None:
    record = session.exec(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key))
    ).first()
    if record is None or record.user_id != user_id or record.revoked:
        return None
    if record.expires_at is not None and record.expires_at < utcnow():
        return None
    return record


def provision_local_owner(
    session: Session,
    *,
    email: str,
    name: str,
    existing_key: str | None = None,
    rotate_key: bool = False,
    expires_in_days: int = LOCAL_KEY_EXPIRY_DAYS,
) -> LocalSetupResult:
    """Create/reuse the local owner and return a usable per-user API key."""
    clean_email, clean_name = _validate_identity(email, name)
    user = session.exec(select(User).where(User.email == clean_email)).first()
    if user is None:
        user = User(
            google_id=f"local:{uuid.uuid4()}",
            email=clean_email,
            name=clean_name,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    elif user.name != clean_name:
        user.name = clean_name
        session.add(user)
        session.commit()
        session.refresh(user)

    ensure_personal_workspace(session, user)

    if existing_key and not rotate_key:
        existing_record = _active_key_for_user(
            session,
            raw_key=existing_key,
            user_id=user.id,
        )
        if existing_record is None:
            raise ValueError(
                "The existing credentials file does not contain an active key "
                "for this owner. Re-run with --rotate-key to replace it."
            )
        return LocalSetupResult(
            user=user,
            api_key=existing_record,
            raw_key=existing_key,
            reused_key=True,
        )

    # A missing credentials file must not leave undiscoverable bootstrap keys
    # active. Revoke prior keys created by this command before issuing another.
    prior_keys = session.exec(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == LOCAL_KEY_NAME,
            ApiKey.revoked.is_(False),
        )
    ).all()
    for prior_key in prior_keys:
        prior_key.revoked = True
        session.add(prior_key)
    if prior_keys:
        session.commit()

    api_key, raw_key = issue_api_key(
        session,
        user_id=user.id,
        name=LOCAL_KEY_NAME,
        expires_in_days=expires_in_days,
    )
    return LocalSetupResult(
        user=user,
        api_key=api_key,
        raw_key=raw_key,
        reused_key=False,
    )


def read_credentials_file(path: Path) -> str | None:
    """Read ``TASKABLE_API_KEY`` from a permission-restricted env file."""
    if not path.exists():
        return None
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError(
            f"{path} is readable by group/other users; run "
            f"`chmod 600 {path}` before continuing."
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TASKABLE_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise ValueError(f"{path} does not contain TASKABLE_API_KEY.")


def write_credentials_file(path: Path, raw_key: str) -> None:
    """Atomically write a local credential with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.parent.chmod(0o700)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"TASKABLE_API_KEY={raw_key}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        if os.name == "posix":
            path.chmod(0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _assert_local_mode(settings: Settings) -> None:
    settings.validate_production()
    if settings.is_production() or not settings.local_auth_enabled:
        raise RuntimeError(
            "Local setup requires LOCAL_AUTH_ENABLED=true and a loopback "
            "HTTP FRONTEND_URL. It is unavailable in production."
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an authenticated local Mouvadah owner and MCP key."
    )
    parser.add_argument("--email", required=True, help="Local owner email.")
    parser.add_argument("--name", required=True, help="Local owner display name.")
    parser.add_argument(
        "--credentials-file",
        type=Path,
        default=Path(
            os.getenv("TASKABLE_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE)
        ).expanduser(),
        help="Owner-only env file that stores TASKABLE_API_KEY.",
    )
    parser.add_argument(
        "--rotate-key",
        action="store_true",
        help="Revoke the prior bootstrap key and issue a replacement.",
    )
    parser.add_argument(
        "--expires-in-days",
        type=int,
        default=LOCAL_KEY_EXPIRY_DAYS,
        help="Lifetime of the local MCP key (default: 365 days).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    try:
        _assert_local_mode(settings)
        existing_key = read_credentials_file(args.credentials_file)
        init_db()
        with Session(engine) as session:
            result = provision_local_owner(
                session,
                email=args.email,
                name=args.name,
                existing_key=existing_key,
                rotate_key=args.rotate_key,
                expires_in_days=args.expires_in_days,
            )
            user_email = result.user.email
            key_prefix = result.api_key.key_prefix
            reused_key = result.reused_key
            raw_key = result.raw_key
        if not reused_key:
            write_credentials_file(args.credentials_file, raw_key)
    except (RuntimeError, ValueError) as exc:
        print(f"Local setup failed: {exc}", file=sys.stderr)
        return 1

    action = "Reused" if reused_key else "Created"
    print(f"{action} local owner: {user_email}")
    print(f"Personal workspace ready; API key prefix: {key_prefix}")
    print(f"Credentials file: {args.credentials_file} (owner-only)")
    print(
        "Use the Local API key from that file to sign in, and point MCP at "
        "the same file with TASKABLE_CREDENTIALS_FILE."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
