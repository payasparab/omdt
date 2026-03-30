"""conversation_messages table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, UUIDPrimaryKeyMixin


class ConversationMessageRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversation_messages"

    conversation_thread_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation_threads.id"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    message_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
