"""Routing and feedback-routing decision models (§11.7–11.8)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import SourceChannel


class FeedbackRoutingDecision(BaseModel):
    """Determines how and where to route a feedback request (§11.8)."""

    thread_id: str
    work_item_id: str
    source_channel: SourceChannel
    preferred_reply_channel: SourceChannel
    participants: list[str] = []
    requires_human_approval: bool = False
    reason: str = ""


class RoutingDecision(BaseModel):
    """An intake routing decision: which agent/queue gets the work-item."""

    id: UUID
    work_item_id: UUID
    route_key: str
    confidence: float | None = None
    reason: str | None = None
