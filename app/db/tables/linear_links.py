"""linear_links table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, UUIDPrimaryKeyMixin


class LinearLinkRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "linear_links"

    omdt_object_type: Mapped[str] = mapped_column(String, nullable=False)
    omdt_object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    linear_object_type: Mapped[str] = mapped_column(String, nullable=False)
    linear_object_id: Mapped[str] = mapped_column(String, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
