"""Add workspace tenancy and project ownership.

Revision ID: 0002_workspace_tenancy
Revises: 0001_pre_tenancy
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_workspace_tenancy"
down_revision: str | Sequence[str] | None = "0001_pre_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    op.create_table(
        "workspace",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspace_slug",
        "workspace",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "workspacemembership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_member",
        ),
    )
    op.create_index(
        "ix_workspacemembership_workspace_id",
        "workspacemembership",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspacemembership_user_id",
        "workspacemembership",
        ["user_id"],
    )

    with op.batch_alter_table(
        "project",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_project_workspace_id_workspace",
            "workspace",
            ["workspace_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_project_workspace_id",
            ["workspace_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "project",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_index("ix_project_workspace_id")
        batch_op.drop_constraint(
            "fk_project_workspace_id_workspace",
            type_="foreignkey",
        )
        batch_op.drop_column("workspace_id")

    op.drop_index(
        "ix_workspacemembership_user_id",
        table_name="workspacemembership",
    )
    op.drop_index(
        "ix_workspacemembership_workspace_id",
        table_name="workspacemembership",
    )
    op.drop_table("workspacemembership")
    op.drop_index("ix_workspace_slug", table_name="workspace")
    op.drop_table("workspace")
