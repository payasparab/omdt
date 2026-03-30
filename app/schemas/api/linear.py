"""Linear sync API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LinearSyncResponse(BaseModel):
    """Response from a Linear sync operation."""

    success: bool
    linear_issue_id: str | None = None
    sync_hash: str | None = None
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


class LinearSyncStatusResponse(BaseModel):
    """Current sync status for a work item."""

    synced: bool
    linear_object_id: str | None = None
    last_sync_at: str | None = None
    sync_hash: str | None = None
    pending_reconciliation_tasks: int = 0
    reason: str | None = None


class LinearWebhookPayload(BaseModel):
    """Inbound Linear webhook payload."""

    action: str = ""
    type: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    url: str | None = None
    createdAt: str | None = None


class LinearWebhookResponse(BaseModel):
    """Response from processing a Linear webhook."""

    processed: bool
    reconciliation_created: bool = False
    conflict: str | None = None
    updates_applied: list[str] = Field(default_factory=list)
    reason: str | None = None
