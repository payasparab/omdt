"""Academic Research Agent input/output schemas per PRD section 10.4."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """Extracted metadata for a single academic paper."""

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url: str | None = None


class PaperSummary(BaseModel):
    """Structured summary of a single paper per section 10.4."""

    paper_id: str
    title: str
    problem_statement: str
    method_summary: str
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    main_results: str = ""
    limitations: list[str] = Field(default_factory=list)
    threats_to_validity: list[str] = Field(default_factory=list)
    relevance_to_omdt_project: str = ""
    recommended_next_steps: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class MethodologyDetail(BaseModel):
    """Extracted methodology from a paper."""

    paper_id: str
    method: str
    dataset: str = ""
    metrics: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    results_summary: str = ""


class LiteratureMatrix(BaseModel):
    """Comparison matrix across multiple papers."""

    papers: list[PaperMetadata] = Field(default_factory=list)
    comparison_dimensions: list[str] = Field(default_factory=list)
    matrix_data: dict[str, dict[str, str]] = Field(default_factory=dict)


class ResearchBrief(BaseModel):
    """Executive or technical research synthesis."""

    summary_type: str  # "executive" | "technical"
    papers: list[PaperMetadata] = Field(default_factory=list)
    synthesis: str = ""
    recommendations: list[str] = Field(default_factory=list)
    follow_up_reading: list[str] = Field(default_factory=list)


class HandoffPayload(BaseModel):
    """Payload for handing off actionable items to another agent."""

    target_agent: str
    summary: str
    actionable_items: list[str] = Field(default_factory=list)
    source_paper_ids: list[str] = Field(default_factory=list)


class AcademicResearchInput(BaseModel):
    """Input data for the Academic Research Agent."""

    action: str  # parse_metadata | summarize | methodology | compare | executive_summary | technical_summary | recommend | hand_off
    source: str | None = None  # URL or file path for single-paper actions
    papers: list[dict] = Field(default_factory=list)  # For multi-paper actions
    target_agent: str | None = None  # For hand_off action


class AcademicResearchOutput(BaseModel):
    """Output of the Academic Research Agent."""

    action: str
    paper_metadata: PaperMetadata | None = None
    paper_summary: PaperSummary | None = None
    methodology: MethodologyDetail | None = None
    literature_matrix: LiteratureMatrix | None = None
    research_brief: ResearchBrief | None = None
    handoff: HandoffPayload | None = None
    recommendations: list[str] = Field(default_factory=list)
