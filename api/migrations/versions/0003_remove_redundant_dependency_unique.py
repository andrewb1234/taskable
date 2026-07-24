"""Remove the dependency-table unique constraint duplicated by its primary key.

Revision ID: 0003_dependency_unique
Revises: 0002_workspace_tenancy
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_dependency_unique"
down_revision: str | Sequence[str] | None = "0002_workspace_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "uq_ticket_dependency"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        # PostgreSQL collapses a UNIQUE constraint that repeats the composite
        # primary key into the primary-key constraint itself.
        return

    unique_names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "ticketdependency"
        )
    }
    if _CONSTRAINT_NAME not in unique_names:
        return

    with op.batch_alter_table("ticketdependency") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    unique_names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(
            "ticketdependency"
        )
    }
    if _CONSTRAINT_NAME in unique_names:
        return
    with op.batch_alter_table("ticketdependency") as batch_op:
        batch_op.create_unique_constraint(
            _CONSTRAINT_NAME,
            ["ticket_id", "depends_on_ticket_id"],
        )
