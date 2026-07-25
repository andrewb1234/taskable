"""Add workspace invitations and access-administration audit events.

Revision ID: 0007_workspace_membership_admin
Revises: 0006_workspace_data_lifecycle
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_workspace_membership_admin"
down_revision: str | Sequence[str] | None = "0006_workspace_data_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_workspacemembership_single_owner",
        "workspacemembership",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("role = 'OWNER'"),
        sqlite_where=sa.text("role = 'OWNER'"),
    )

    op.create_table(
        "workspaceinvitation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(token_hash) = 64",
            name="ck_workspace_invitation_token_hash",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_workspace_invitation_expiry",
        ),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'MEMBER', 'VIEWER')",
            name="ck_workspace_invitation_role",
        ),
        sa.CheckConstraint(
            "NOT (accepted_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_workspace_invitation_terminal_state",
        ),
        sa.CheckConstraint(
            "(accepted_at IS NULL AND accepted_by_user_id IS NULL) "
            "OR (accepted_at IS NOT NULL AND accepted_by_user_id IS NOT NULL)",
            name="ck_workspace_invitation_acceptance_complete",
        ),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspaceinvitation_workspace_id",
        "workspaceinvitation",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspaceinvitation_email",
        "workspaceinvitation",
        ["email"],
    )
    op.create_index(
        "ix_workspaceinvitation_token_hash",
        "workspaceinvitation",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_workspaceinvitation_created_by_user_id",
        "workspaceinvitation",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_workspaceinvitation_expires_at",
        "workspaceinvitation",
        ["expires_at"],
    )
    op.create_index(
        "ix_workspaceinvitation_accepted_at",
        "workspaceinvitation",
        ["accepted_at"],
    )
    op.create_index(
        "ix_workspaceinvitation_accepted_by_user_id",
        "workspaceinvitation",
        ["accepted_by_user_id"],
    )
    op.create_index(
        "ix_workspaceinvitation_revoked_at",
        "workspaceinvitation",
        ["revoked_at"],
    )

    op.create_table(
        "workspacemembershipevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("invitation_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "action IN ("
            "'INVITATION_CREATED', "
            "'INVITATION_REVOKED', "
            "'INVITATION_ACCEPTED', "
            "'ROLE_CHANGED', "
            "'MEMBER_REMOVED', "
            "'OWNERSHIP_TRANSFERRED'"
            ")",
            name="ck_workspace_membership_action",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "workspace_id",
        "action",
        "actor_user_id",
        "subject_user_id",
        "invitation_id",
    ):
        op.create_index(
            f"ix_workspacemembershipevent_{column}",
            "workspacemembershipevent",
            [column],
        )


def downgrade() -> None:
    for column in (
        "invitation_id",
        "subject_user_id",
        "actor_user_id",
        "action",
        "workspace_id",
    ):
        op.drop_index(
            f"ix_workspacemembershipevent_{column}",
            table_name="workspacemembershipevent",
        )
    op.drop_table("workspacemembershipevent")

    for index_name in (
        "ix_workspaceinvitation_revoked_at",
        "ix_workspaceinvitation_accepted_by_user_id",
        "ix_workspaceinvitation_accepted_at",
        "ix_workspaceinvitation_expires_at",
        "ix_workspaceinvitation_created_by_user_id",
        "ix_workspaceinvitation_token_hash",
        "ix_workspaceinvitation_email",
        "ix_workspaceinvitation_workspace_id",
    ):
        op.drop_index(index_name, table_name="workspaceinvitation")
    op.drop_table("workspaceinvitation")
    op.drop_index(
        "uq_workspacemembership_single_owner",
        table_name="workspacemembership",
    )
