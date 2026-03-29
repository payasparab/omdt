"""conversation_threads table."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationThreadRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_threads"

    work_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_items.id"), nullable=False
    )
    source_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    source_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
