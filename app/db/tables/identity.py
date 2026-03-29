"""identity_people table."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PersonRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "identity_people"

    person_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    primary_email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    alternate_emails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outlook_upn: Mapped[str | None] = mapped_column(String, nullable=True)
    roles: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preferred_notification_channel: Mapped[str] = mapped_column(
        String, nullable=False, default="email"
    )
