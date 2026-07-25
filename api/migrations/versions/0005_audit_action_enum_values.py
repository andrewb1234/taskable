"""Repair PostgreSQL audit-action enum values used by coordination routes.

Revision ID: 0005_audit_action_enum_values
Revises: 0004_session_key_security
Create Date: 2026-07-25

Some pre-Alembic PostgreSQL databases created ``auditaction`` before ticket
claim/requeue audit actions existed. The baseline migration was later stamped
onto those databases without recreating the native enum, and Alembic schema
comparison does not detect missing enum members. SQLite stores these values as
strings and needs no repair.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_audit_action_enum_values"
down_revision: str | Sequence[str] | None = "0004_session_key_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'TICKET_CLAIMED'"
    )
    op.execute(
        "ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'TICKET_REQUEUED'"
    )


def downgrade() -> None:
    # PostgreSQL cannot remove an enum member without replacing the type.
    # Keeping the harmless superset is safer than rewriting a live audit
    # column during a development downgrade. Production rollback restores a
    # verified backup rather than relying on destructive down migrations.
    return
