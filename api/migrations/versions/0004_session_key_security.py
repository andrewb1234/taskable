"""Add revocable browser sessions and workspace-scoped API keys.

Revision ID: 0004_session_key_security
Revises: 0003_dependency_unique
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_session_key_security"
down_revision: str | Sequence[str] | None = "0003_dependency_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    op.create_table(
        "browsersession",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_browsersession_user_id",
        "browsersession",
        ["user_id"],
    )
    op.create_index(
        "ix_browsersession_expires_at",
        "browsersession",
        ["expires_at"],
    )
    op.create_index(
        "ix_browsersession_revoked_at",
        "browsersession",
        ["revoked_at"],
    )

    with op.batch_alter_table(
        "apikey",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "scopes",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[\"read\", \"write\"]'"),
            )
        )
        batch_op.create_foreign_key(
            "fk_apikey_workspace_id_workspace",
            "workspace",
            ["workspace_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_apikey_workspace_id",
            ["workspace_id"],
        )

    # Preserve legacy keys only when ownership is unambiguous. Keys belonging
    # to users with zero or multiple workspaces fail closed until reissued.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE apikey SET workspace_id = ("
            "SELECT MIN(workspace_id) FROM workspacemembership "
            "WHERE workspacemembership.user_id = apikey.user_id"
            ") WHERE ("
            "SELECT COUNT(*) FROM workspacemembership "
            "WHERE workspacemembership.user_id = apikey.user_id"
            ") = 1"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE apikey SET revoked = :revoked "
            "WHERE workspace_id IS NULL"
        ),
        {"revoked": True},
    )

    op.create_table(
        "apikeyproject",
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["apikey.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("api_key_id", "project_id"),
    )
    op.create_index(
        "ix_apikeyproject_api_key_id",
        "apikeyproject",
        ["api_key_id"],
    )
    op.create_index(
        "ix_apikeyproject_project_id",
        "apikeyproject",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_apikeyproject_project_id",
        table_name="apikeyproject",
    )
    op.drop_index(
        "ix_apikeyproject_api_key_id",
        table_name="apikeyproject",
    )
    op.drop_table("apikeyproject")

    with op.batch_alter_table(
        "apikey",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_index("ix_apikey_workspace_id")
        batch_op.drop_constraint(
            "fk_apikey_workspace_id_workspace",
            type_="foreignkey",
        )
        batch_op.drop_column("scopes")
        batch_op.drop_column("workspace_id")

    op.drop_index(
        "ix_browsersession_revoked_at",
        table_name="browsersession",
    )
    op.drop_index(
        "ix_browsersession_expires_at",
        table_name="browsersession",
    )
    op.drop_index(
        "ix_browsersession_user_id",
        table_name="browsersession",
    )
    op.drop_table("browsersession")
