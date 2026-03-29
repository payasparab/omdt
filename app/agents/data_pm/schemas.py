"""Data PM agent input/output schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DataPMInput(BaseModel):
    """Input data for the Data PM Agent."""

    work_item_id: str
    title: str
    description: str
    route_key: str
    priority: str = "medium"
    requester: str | None = None
    audience: str | None = None
    business_goal: str | None = None
    source_data: str | None = None
    constraints: list[str] = Field(default_factory=list)
    related_work_items: list[str] = Field(default_factory=list)


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion for the PRD."""

    criterion_id: str
    description: str
    verification_method: str = ""


class Milestone(BaseModel):
    """A project milestone."""

    name: str
    description: str = ""
    target_date: str | None = None


class Risk(BaseModel):
    """A project risk."""

    description: str
    likelihood: str = "medium"  # low, medium, high
    impact: str = "medium"  # low, medium, high
    mitigation: str = ""


class PRDDraftOutput(BaseModel):
    """Output of the Data PM Agent — a structured PRD draft."""

    work_item_id: str
    prd_title: str
    executive_summary: str
    business_goal: str
    scope: str
    out_of_scope: str = ""
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    handoff_to: str | None = None
    revision_number: int = 1
