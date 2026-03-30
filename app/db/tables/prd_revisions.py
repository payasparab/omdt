"""prd_revisions table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, UUIDPrimaryKeyMixin


class PRDRevisionRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prd_revisions"

    work_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("work_items.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifacts.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
