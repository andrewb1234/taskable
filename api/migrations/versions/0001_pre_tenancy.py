"""Create the supported 0.1.0 pre-tenancy schema.

Revision ID: 0001_pre_tenancy
Revises:
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_pre_tenancy"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

actor_role = sa.Enum("HUMAN", "AGENT", name="actorrole")
audit_action = sa.Enum(
    "STATUS_UPDATE",
    "CONTENT_UPDATE",
    "MR_LINKED",
    "TICKET_CLAIMED",
    "TICKET_REQUEUED",
    name="auditaction",
)
knowledge_node_type = sa.Enum(
    "RAW",
    "SUMMARY",
    "PRD",
    "TDD",
    name="knowledgenodetype",
)
subproject_status = sa.Enum(
    "PLANNING",
    "ACTIVE",
    "COMPLETED",
    name="subprojectstatus",
)
ticket_assignee = sa.Enum(
    "HUMAN",
    "AGENT",
    "UNASSIGNED",
    name="ticketassignee",
)
ticket_status = sa.Enum(
    "TODO",
    "IN_PROGRESS",
    "BLOCKED",
    "REVIEW",
    "DONE",
    name="ticketstatus",
)


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_name", "project", ["name"])

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("google_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_google_id", "user", ["google_id"], unique=True)
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "subproject",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("context_brief", sa.String(), nullable=False),
        sa.Column("status", subproject_status, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subproject_project_id",
        "subproject",
        ["project_id"],
    )

    op.create_table(
        "agentsession",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("loaded_node_ids", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("handoff_note", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agentsession_project_id",
        "agentsession",
        ["project_id"],
    )

    op.create_table(
        "ticket",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subproject_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("assignee", ticket_assignee, nullable=False),
        sa.Column("mr_link", sa.String(), nullable=True),
        sa.Column("blocked_by", sa.String(), nullable=True),
        sa.Column("blocked_reason", sa.String(), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("claimed_by", sa.String(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["subproject_id"], ["subproject.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_subproject_id",
        "ticket",
        ["subproject_id"],
    )
    op.create_index("ix_ticket_claimed_by", "ticket", ["claimed_by"])

    op.create_table(
        "knowledgenode",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("node_type", knowledge_node_type, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_by", actor_role, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["knowledgenode.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["knowledgenode.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledgenode_project_id",
        "knowledgenode",
        ["project_id"],
    )
    op.create_index(
        "ix_knowledgenode_parent_id",
        "knowledgenode",
        ["parent_id"],
    )
    op.create_index(
        "ix_knowledgenode_superseded_by",
        "knowledgenode",
        ["superseded_by"],
    )

    op.create_table(
        "apikey",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apikey_user_id", "apikey", ["user_id"])
    op.create_index("ix_apikey_key_prefix", "apikey", ["key_prefix"])
    op.create_index(
        "ix_apikey_key_hash",
        "apikey",
        ["key_hash"],
        unique=True,
    )

    op.create_table(
        "comment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author", actor_role, nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comment_ticket_id", "comment", ["ticket_id"])

    op.create_table(
        "auditlog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("actor", actor_role, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditlog_ticket_id", "auditlog", ["ticket_id"])

    op.create_table(
        "ticketdependency",
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("depends_on_ticket_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["depends_on_ticket_id"],
            ["ticket.id"],
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("ticket_id", "depends_on_ticket_id"),
        sa.UniqueConstraint(
            "ticket_id",
            "depends_on_ticket_id",
            name="uq_ticket_dependency",
        ),
    )
    op.create_index(
        "ix_ticketdependency_ticket_id",
        "ticketdependency",
        ["ticket_id"],
    )
    op.create_index(
        "ix_ticketdependency_depends_on_ticket_id",
        "ticketdependency",
        ["depends_on_ticket_id"],
    )

    op.create_table(
        "knowledgeproposal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("proposed_by", sa.String(), nullable=False),
        sa.Column("proposed_changes", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["knowledgenode.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledgeproposal_node_id",
        "knowledgeproposal",
        ["node_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledgeproposal_node_id",
        table_name="knowledgeproposal",
    )
    op.drop_table("knowledgeproposal")
    op.drop_index(
        "ix_ticketdependency_depends_on_ticket_id",
        table_name="ticketdependency",
    )
    op.drop_index(
        "ix_ticketdependency_ticket_id",
        table_name="ticketdependency",
    )
    op.drop_table("ticketdependency")
    op.drop_index("ix_auditlog_ticket_id", table_name="auditlog")
    op.drop_table("auditlog")
    op.drop_index("ix_comment_ticket_id", table_name="comment")
    op.drop_table("comment")
    op.drop_index("ix_apikey_key_hash", table_name="apikey")
    op.drop_index("ix_apikey_key_prefix", table_name="apikey")
    op.drop_index("ix_apikey_user_id", table_name="apikey")
    op.drop_table("apikey")
    op.drop_index(
        "ix_knowledgenode_superseded_by",
        table_name="knowledgenode",
    )
    op.drop_index(
        "ix_knowledgenode_parent_id",
        table_name="knowledgenode",
    )
    op.drop_index(
        "ix_knowledgenode_project_id",
        table_name="knowledgenode",
    )
    op.drop_table("knowledgenode")
    op.drop_index("ix_ticket_claimed_by", table_name="ticket")
    op.drop_index("ix_ticket_subproject_id", table_name="ticket")
    op.drop_table("ticket")
    op.drop_index(
        "ix_agentsession_project_id",
        table_name="agentsession",
    )
    op.drop_table("agentsession")
    op.drop_index(
        "ix_subproject_project_id",
        table_name="subproject",
    )
    op.drop_table("subproject")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_index("ix_user_google_id", table_name="user")
    op.drop_table("user")
    op.drop_index("ix_project_name", table_name="project")
    op.drop_table("project")

    if op.get_bind().dialect.name == "postgresql":
        for enum_type in (
            audit_action,
            actor_role,
            knowledge_node_type,
            subproject_status,
            ticket_assignee,
            ticket_status,
        ):
            enum_type.drop(op.get_bind(), checkfirst=True)
