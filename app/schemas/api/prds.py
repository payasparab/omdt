"""PRD API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PRDDraftRequest(BaseModel):
    """Request to create or update a PRD draft."""

    content: str = Field(..., min_length=1, description="PRD markdown content")
    author: str = Field(..., description="Person key of the author")


class PRDFeedbackRequest(BaseModel):
    """Request to submit feedback on a PRD revision."""

    feedback: str = Field(..., min_length=1, description="Feedback text")
    reviewer: str | None = Field(default=None, description="Person key of the reviewer")


class PRDApproveRequest(BaseModel):
    """Request to approve a PRD, making it immutable."""

    approver: str = Field(..., description="Person key of the approver")


class PRDResponse(BaseModel):
    """PRD representation (latest or specific revision)."""

    id: str
    work_item_id: str
    revision_number: int
    content: str
    author: str
    status: str
    artifact_id: str | None = None
    created_at: datetime | None = None
    frozen_at: datetime | None = None


# Alias used by existing router
PRDRevisionResponse = PRDResponse
