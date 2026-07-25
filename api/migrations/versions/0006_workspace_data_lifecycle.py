"""Add recoverable workspace deletion and a retained lifecycle ledger.

Revision ID: 0006_workspace_data_lifecycle
Revises: 0005_audit_action_enum_values
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_workspace_data_lifecycle"
down_revision: str | Sequence[str] | None = "0005_audit_action_enum_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspace") as batch_op:
        batch_op.add_column(
            sa.Column("deletion_requested_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("purge_after", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deletion_requested_by", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deletion_export_sha256", sa.String(), nullable=True)
        )
        batch_op.create_index(
            "ix_workspace_deletion_requested_at",
            ["deletion_requested_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_workspace_purge_after",
            ["purge_after"],
            unique=False,
        )
        batch_op.create_check_constraint(
            "ck_workspace_deletion_state_complete",
            "("
            "deletion_requested_at IS NULL "
            "AND purge_after IS NULL "
            "AND deletion_requested_by IS NULL "
            "AND deletion_export_sha256 IS NULL"
            ") OR ("
            "deletion_requested_at IS NOT NULL "
            "AND purge_after IS NOT NULL "
            "AND deletion_requested_by IS NOT NULL "
            "AND deletion_export_sha256 IS NOT NULL"
            ")",
        )
        batch_op.create_check_constraint(
            "ck_workspace_purge_after_request",
            "purge_after IS NULL OR purge_after > deletion_requested_at",
        )
        batch_op.create_check_constraint(
            "ck_workspace_deletion_export_sha256",
            "deletion_export_sha256 IS NULL "
            "OR length(deletion_export_sha256) = 64",
        )

    op.create_table(
        "workspacelifecycleevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "action IN ("
            "'EXPORTED', "
            "'DELETION_SCHEDULED', "
            "'DELETION_RESTORED', "
            "'PURGED'"
            ")",
            name="ck_workspace_lifecycle_action",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspacelifecycleevent_workspace_id",
        "workspacelifecycleevent",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspacelifecycleevent_action",
        "workspacelifecycleevent",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_workspacelifecycleevent_actor_user_id",
        "workspacelifecycleevent",
        ["actor_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspacelifecycleevent_actor_user_id",
        table_name="workspacelifecycleevent",
    )
    op.drop_index(
        "ix_workspacelifecycleevent_action",
        table_name="workspacelifecycleevent",
    )
    op.drop_index(
        "ix_workspacelifecycleevent_workspace_id",
        table_name="workspacelifecycleevent",
    )
    op.drop_table("workspacelifecycleevent")

    with op.batch_alter_table("workspace") as batch_op:
        batch_op.drop_constraint(
            "ck_workspace_deletion_export_sha256",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_workspace_purge_after_request",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_workspace_deletion_state_complete",
            type_="check",
        )
        batch_op.drop_index("ix_workspace_purge_after")
        batch_op.drop_index("ix_workspace_deletion_requested_at")
        batch_op.drop_column("deletion_export_sha256")
        batch_op.drop_column("deletion_requested_by")
        batch_op.drop_column("purge_after")
        batch_op.drop_column("deletion_requested_at")
