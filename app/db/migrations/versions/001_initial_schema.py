"""Initial schema — core OMDT tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String, unique=True, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False, server_default="new"),
        sa.Column("owner_person_key", sa.String, nullable=True),
        sa.Column("linear_project_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- work_items ---
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("work_type", sa.String, nullable=False),
        sa.Column("canonical_state", sa.String, nullable=False, server_default="new"),
        sa.Column("priority", sa.String, nullable=False, server_default="medium"),
        sa.Column("source_channel", sa.String, nullable=True),
        sa.Column("source_external_id", sa.String, nullable=True),
        sa.Column("requester_person_key", sa.String, nullable=True),
        sa.Column("owner_person_key", sa.String, nullable=True),
        sa.Column("route_key", sa.String, nullable=True),
        sa.Column("risk_level", sa.String, nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_approval", sa.Boolean, server_default="false"),
        sa.Column("latest_prd_revision_id", sa.String(36), nullable=True),
        sa.Column("linear_issue_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- artifacts ---
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_type", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=True),
        sa.Column("storage_uri", sa.String, nullable=False),
        sa.Column("mime_type", sa.String, nullable=True),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("created_by_actor", sa.String, nullable=True),
        sa.Column("source_run_id", sa.String(36), nullable=True),
        sa.Column("linked_object_type", sa.String, nullable=True),
        sa.Column("linked_object_id", sa.String(36), nullable=True),
        sa.Column("approval_status", sa.String, nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- artifact_links ---
    op.create_table(
        "artifact_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("linked_object_type", sa.String, nullable=False),
        sa.Column("linked_object_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- conversation_threads ---
    op.create_table(
        "conversation_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("source_channel", sa.String, nullable=True),
        sa.Column("source_external_id", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- conversation_messages ---
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_thread_id", sa.String(36), sa.ForeignKey("conversation_threads.id"), nullable=False),
        sa.Column("actor_id", sa.String, nullable=False),
        sa.Column("actor_type", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_channel", sa.String, nullable=True),
        sa.Column("message_hash", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- prd_revisions ---
    op.create_table(
        "prd_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.id"), nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- identity_people ---
    op.create_table(
        "identity_people",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_key", sa.String, unique=True, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("primary_email", sa.String, unique=True, nullable=False),
        sa.Column("alternate_emails", sa.JSON, nullable=True),
        sa.Column("outlook_upn", sa.String, nullable=True),
        sa.Column("roles", sa.JSON, nullable=True),
        sa.Column("preferred_notification_channel", sa.String, nullable=False, server_default="email"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- audit_events ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sequence_number", sa.BigInteger, unique=True, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_name", sa.String, nullable=False),
        sa.Column("actor_type", sa.String, nullable=False),
        sa.Column("actor_id", sa.String, nullable=False),
        sa.Column("correlation_id", sa.String, nullable=False, index=True),
        sa.Column("object_type", sa.String, nullable=False),
        sa.Column("object_id", sa.String, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=False),
        sa.Column("tool_name", sa.String, nullable=True),
        sa.Column("approval_id", sa.String, nullable=True),
        sa.Column("prev_event_hash", sa.String, nullable=True),
        sa.Column("event_hash", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # --- linear_links ---
    op.create_table(
        "linear_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("omdt_object_type", sa.String, nullable=False),
        sa.Column("omdt_object_id", sa.String(36), nullable=False),
        sa.Column("linear_object_type", sa.String, nullable=False),
        sa.Column("linear_object_id", sa.String, nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_hash", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("linear_links")
    op.drop_table("audit_events")
    op.drop_table("identity_people")
    op.drop_table("prd_revisions")
    op.drop_table("conversation_messages")
    op.drop_table("conversation_threads")
    op.drop_table("artifact_links")
    op.drop_table("artifacts")
    op.drop_table("work_items")
    op.drop_table("projects")
