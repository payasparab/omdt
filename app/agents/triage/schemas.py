"""Triage agent input/output schemas per PRD section 10.3."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import CanonicalState, Priority, WorkItemType


class TriageInput(BaseModel):
    """Input data for the Triage Agent."""

    message_body: str
    subject: str | None = None
    source_channel: str | None = None
    requester_identity: str | None = None
    prior_thread_history: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    related_work_item_ids: list[str] = Field(default_factory=list)
    related_project_ids: list[str] = Field(default_factory=list)


# The eight fields that must be present for a request to be fully triaged.
REQUIRED_CLARIFICATION_FIELDS: list[str] = [
    "business_goal",
    "decision_or_use_case",
    "requested_output",
    "expected_audience",
    "urgency",
    "source_data",
    "system_or_environment",
    "owner_or_approver",
]


class ClarificationItem(BaseModel):
    """A single missing-info item with a question to ask."""

    field_name: str
    question: str


class TriageOutput(BaseModel):
    """Output of the Triage Agent per section 10.3."""

    normalized_title: str
    work_item_type: WorkItemType
    priority: Priority = Priority.MEDIUM
    route_key: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    required_agents: list[str] = Field(default_factory=list)
    missing_info_checklist: list[str] = Field(default_factory=list)
    clarification_questions: list[ClarificationItem] = Field(default_factory=list)
    linear_sync_intent: bool = True
    recommended_next_state: CanonicalState = CanonicalState.READY_FOR_PRD
