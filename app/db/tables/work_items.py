"""work_items table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkItemRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_items"

    project_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_type: Mapped[str] = mapped_column(String, nullable=False)
    canonical_state: Mapped[str] = mapped_column(String, nullable=False, default="new")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    source_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    source_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    requester_person_key: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_person_key: Mapped[str | None] = mapped_column(String, nullable=True)
    route_key: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    latest_prd_revision_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    linear_issue_id: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
