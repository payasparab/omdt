"""Linear synchronisation link model (Appendix F)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LinearLink(BaseModel):
    """Maps an OMDT object to its Linear counterpart."""

    id: UUID
    omdt_object_type: str
    omdt_object_id: UUID
    linear_object_type: str
    linear_object_id: str
    last_sync_at: datetime | None = None
    sync_hash: str | None = None
