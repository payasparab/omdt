"""Intake API schemas — request/response models for message ingestion."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AttachmentRef(BaseModel):
    """Reference to an attachment on an intake message."""

    filename: str
    content_type: str | None = None
    url: str | None = None
    size_bytes: int | None = None


class IntakeMessageRequest(BaseModel):
    """Inbound message from any channel (email, Linear, Notion, API)."""

    message: str = Field(..., min_length=1, description="The message body / request text")
    subject: str | None = Field(default=None, description="Email subject or thread title")
    source_channel: str = Field(
        ..., description="Origin channel: email, linear, notion, api, cli"
    )
    requester: str = Field(..., description="Person key or email of the requester")
    external_id: str | None = Field(
        default=None, description="External system ID (e.g. email message-id, Linear issue ID)"
    )
    attachments: list[AttachmentRef] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class CLIIntakeRequest(BaseModel):
    """Simplified intake request from the CLI."""

    message: str = Field(..., min_length=1, description="The request text")
    requester: str = Field(..., description="Person key of the CLI user")


class IntakeMessageResponse(BaseModel):
    """Response after processing an intake message."""

    work_item_id: str
    title: str
    canonical_state: str
    source_channel: str
    message: str = "Intake processed successfully"
