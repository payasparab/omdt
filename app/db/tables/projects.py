"""projects table."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="new")
    owner_person_key: Mapped[str | None] = mapped_column(String, nullable=True)
    linear_project_id: Mapped[str | None] = mapped_column(String, nullable=True)
