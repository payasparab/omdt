"""artifacts and artifact_links tables."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.tables.base import Base, UUIDPrimaryKeyMixin


class ArtifactRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "artifacts"

    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_uri: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_actor: Mapped[str | None] = mapped_column(String, nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    linked_object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approval_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ArtifactLinkRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "artifact_links"

    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artifacts.id"), nullable=False
    )
    linked_object_type: Mapped[str] = mapped_column(String, nullable=False)
    linked_object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
