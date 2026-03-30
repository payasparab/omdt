"""Technical Writer Agent input/output schemas per PRD section 10.5."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.ids import generate_id


class DocumentOutput(BaseModel):
    """Output schema for all Technical Writer documents per section 10.5."""

    document_id: str = Field(default_factory=generate_id)
    document_type: str  # executive_summary | technical_memo | runbook | release_notes | sop | user_guide
    audience: str = ""
    title: str = ""
    executive_summary: str = ""
    source_artifacts: list[str] = Field(default_factory=list)
    key_changes_or_findings: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    procedure_or_narrative: str = ""
    risks_and_caveats: list[str] = Field(default_factory=list)
    glossary: dict[str, str] = Field(default_factory=dict)
    reviewers: list[str] = Field(default_factory=list)
    publication_targets: list[str] = Field(default_factory=list)


class MissingFact(BaseModel):
    """A gap detected in source material that needs clarification."""

    field: str
    question: str
    source_artifact: str | None = None


class ReviewChecklistItem(BaseModel):
    """A single item on a document review checklist."""

    item: str
    checked: bool = False


class TechnicalWriterInput(BaseModel):
    """Input data for the Technical Writer Agent."""

    action: str  # executive_summary | technical_memo | runbook | release_notes | sop | user_guide | detect_missing | review_checklist
    source_artifacts: list[str] = Field(default_factory=list)
    audience: str = "technical"
    title: str | None = None
    deployment_record: dict | None = None
    changes: list[str] = Field(default_factory=list)
    process_description: str | None = None
    feature: str | None = None
    document: dict | None = None


class TechnicalWriterOutput(BaseModel):
    """Output of the Technical Writer Agent."""

    action: str
    document: DocumentOutput | None = None
    missing_facts: list[MissingFact] = Field(default_factory=list)
    review_checklist: list[ReviewChecklistItem] = Field(default_factory=list)
