"""Conversation and feedback domain models (§11.2)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import ActorType, SourceChannel


class ConversationThread(BaseModel):
    """A conversation thread attached to a work-item."""

    id: UUID
    work_item_id: UUID
    source_channel: SourceChannel | None = None
    source_external_id: str | None = None
    status: str = "open"
    created_at: datetime
    updated_at: datetime


class ConversationMessage(BaseModel):
    """A single message within a conversation thread."""

    id: UUID
    conversation_thread_id: UUID
    actor_id: str
    actor_type: ActorType
    content: str
    source_channel: SourceChannel | None = None
    message_hash: str | None = None
    created_at: datetime


class FeedbackRequest(BaseModel):
    """A request for feedback on a PRD revision."""

    id: UUID
    prd_revision_id: UUID | None = None
    work_item_id: UUID
    requested_from: list[str] = []
    requested_channels: list[SourceChannel] = []
    status: str = "pending"
    deadline_at: datetime | None = None
    created_at: datetime


class FeedbackResponse(BaseModel):
    """A response to a feedback request."""

    id: UUID
    feedback_request_id: UUID
    respondent_person_key: str
    response_channel: SourceChannel | None = None
    content: str
    prd_revision_id_informed: UUID | None = None
    created_at: datetime


class ClarificationChecklist(BaseModel):
    """Tracks clarification items for a work-item."""

    id: UUID
    work_item_id: UUID
    items: list[dict[str, str | bool]] = []
    status: str = "open"
    created_at: datetime
    updated_at: datetime
