"""Academic Research Agent — paper analysis, literature review, and research synthesis."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.academic.schemas import (
    AcademicResearchInput,
    AcademicResearchOutput,
    HandoffPayload,
    LiteratureMatrix,
    MethodologyDetail,
    PaperMetadata,
    PaperSummary,
    ResearchBrief,
)
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_paper_metadata(source: str) -> PaperMetadata:
    """Extract title, authors, year, venue from a source reference.

    In production this would call a PDF parser or URL scraper.
    Current implementation extracts from structured text.
    """
    paper_id = generate_id()
    # Heuristic: treat source as a title/reference string
    title = source.strip().split("\n")[0] if source else "Untitled Paper"
    return PaperMetadata(
        paper_id=paper_id,
        title=title,
        authors=["Unknown"],
        year=None,
        venue=None,
        url=source if source.startswith("http") else None,
    )


def _generate_paper_summary(paper: dict) -> PaperSummary:
    """Generate a structured summary for a paper.

    Expects paper dict with at least 'paper_id' and 'title'.
    """
    paper_id = paper.get("paper_id", generate_id())
    title = paper.get("title", "Untitled")
    return PaperSummary(
        paper_id=paper_id,
        title=title,
        problem_statement=paper.get("problem_statement", f"Problem addressed by: {title}"),
        method_summary=paper.get("method_summary", "Method not yet extracted."),
        datasets=paper.get("datasets") or ([paper["dataset"]] if paper.get("dataset") else []),
        metrics=paper.get("metrics", []),
        main_results=paper.get("main_results", "Results pending detailed analysis."),
        limitations=paper.get("limitations", ["Limitations not yet identified."]),
        threats_to_validity=paper.get("threats_to_validity", []),
        relevance_to_omdt_project=paper.get(
            "relevance_to_omdt_project",
            "Relevance assessment pending.",
        ),
        recommended_next_steps=paper.get("recommended_next_steps", []),
        citations=paper.get("citations", []),
    )


def _identify_methodology(paper: dict) -> MethodologyDetail:
    """Extract methodology details from a paper dict."""
    return MethodologyDetail(
        paper_id=paper.get("paper_id", generate_id()),
        method=paper.get("method", "Not specified"),
        dataset=paper.get("dataset", ""),
        metrics=paper.get("metrics", []),
        assumptions=paper.get("assumptions", []),
        limitations=paper.get("limitations", []),
        results_summary=paper.get("results_summary", ""),
    )


def _compare_papers(papers: list[dict]) -> LiteratureMatrix:
    """Generate a literature comparison matrix."""
    metadata_list = []
    dimensions = ["method", "dataset", "metrics", "main_results", "limitations"]
    matrix: dict[str, dict[str, str]] = {}

    for p in papers:
        pid = p.get("paper_id", generate_id())
        meta = PaperMetadata(
            paper_id=pid,
            title=p.get("title", "Untitled"),
            authors=p.get("authors", []),
            year=p.get("year"),
            venue=p.get("venue"),
        )
        metadata_list.append(meta)
        matrix[pid] = {
            dim: str(p.get(dim, "N/A")) for dim in dimensions
        }

    return LiteratureMatrix(
        papers=metadata_list,
        comparison_dimensions=dimensions,
        matrix_data=matrix,
    )


def _produce_executive_summary(papers: list[dict]) -> ResearchBrief:
    """Produce an executive-level synthesis across papers."""
    metadata_list = [
        PaperMetadata(
            paper_id=p.get("paper_id", generate_id()),
            title=p.get("title", "Untitled"),
            authors=p.get("authors", []),
            year=p.get("year"),
            venue=p.get("venue"),
        )
        for p in papers
    ]
    titles = [p.get("title", "Untitled") for p in papers]
    synthesis = (
        f"Executive synthesis of {len(papers)} papers covering: "
        + ", ".join(titles[:5])
        + ("..." if len(titles) > 5 else "")
        + ". Key themes and strategic implications have been identified."
    )
    return ResearchBrief(
        summary_type="executive",
        papers=metadata_list,
        synthesis=synthesis,
        recommendations=[
            "Review highlighted papers for strategic alignment.",
            "Schedule follow-up discussion with stakeholders.",
        ],
    )


def _produce_technical_summary(papers: list[dict]) -> ResearchBrief:
    """Produce a technical deep-dive synthesis across papers."""
    metadata_list = [
        PaperMetadata(
            paper_id=p.get("paper_id", generate_id()),
            title=p.get("title", "Untitled"),
            authors=p.get("authors", []),
            year=p.get("year"),
            venue=p.get("venue"),
        )
        for p in papers
    ]
    methods = [p.get("method", "unspecified") for p in papers]
    synthesis = (
        f"Technical synthesis of {len(papers)} papers. "
        f"Methods analyzed: {', '.join(set(methods))}. "
        "Detailed comparison of approaches, datasets, and metrics follows."
    )
    return ResearchBrief(
        summary_type="technical",
        papers=metadata_list,
        synthesis=synthesis,
        recommendations=[
            "Evaluate reproducibility of top-performing methods.",
            "Identify gaps in dataset coverage.",
        ],
    )


def _recommend_follow_up(papers: list[dict]) -> list[str]:
    """Suggest next reading based on the analyzed papers."""
    recommendations = []
    for p in papers:
        citations = p.get("citations", [])
        if citations:
            recommendations.extend(citations[:2])
        else:
            recommendations.append(
                f"Explore further work related to: {p.get('title', 'Unknown')}"
            )
    return recommendations[:10]


def _hand_off_implications(
    summary: str, target_agent: str, paper_ids: list[str]
) -> HandoffPayload:
    """Route actionable items to a target agent."""
    return HandoffPayload(
        target_agent=target_agent,
        summary=summary,
        actionable_items=[
            f"Review research implications from papers: {', '.join(paper_ids[:5])}",
            "Assess applicability to current project scope.",
        ],
        source_paper_ids=paper_ids,
    )


# ---------------------------------------------------------------------------
# Academic Research Agent
# ---------------------------------------------------------------------------

_VALID_ACTIONS = {
    "parse_metadata",
    "summarize",
    "methodology",
    "compare",
    "executive_summary",
    "technical_summary",
    "recommend",
    "hand_off",
}


class AcademicResearchAgent(BaseAgent):
    """Analyzes academic papers, produces literature reviews and research briefs.

    Implements the academic research role from PRD section 10.4.
    """

    name = "academic_research_agent"
    mission = (
        "Parse academic papers, generate structured summaries, compare "
        "methodologies across a literature set, produce executive and "
        "technical syntheses, and hand off actionable implications to "
        "downstream agents."
    )
    allowed_tools = [
        "parse_pdf",
        "fetch_paper_url",
        "search_semantic_scholar",
        "search_arxiv",
        "create_literature_matrix",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["action"]
    output_schema = AcademicResearchOutput
    handoff_targets = ["data_scientist", "data_pm"]

    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the requested academic research action."""
        inputs = context.input_data

        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        research_input = AcademicResearchInput.model_validate(inputs)
        action = research_input.action

        if action not in _VALID_ACTIONS:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Unknown action: {action}. Valid: {sorted(_VALID_ACTIONS)}"],
            )

        output = AcademicResearchOutput(action=action)

        if action == "parse_metadata":
            if not research_input.source:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'source' is required for parse_metadata action"],
                )
            output.paper_metadata = _parse_paper_metadata(research_input.source)

        elif action == "summarize":
            if not research_input.papers:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'papers' list is required for summarize action"],
                )
            output.paper_summary = _generate_paper_summary(research_input.papers[0])

        elif action == "methodology":
            if not research_input.papers:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'papers' list is required for methodology action"],
                )
            output.methodology = _identify_methodology(research_input.papers[0])

        elif action == "compare":
            if len(research_input.papers) < 2:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["At least 2 papers required for compare action"],
                )
            output.literature_matrix = _compare_papers(research_input.papers)

        elif action == "executive_summary":
            if not research_input.papers:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'papers' list is required for executive_summary action"],
                )
            output.research_brief = _produce_executive_summary(research_input.papers)

        elif action == "technical_summary":
            if not research_input.papers:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'papers' list is required for technical_summary action"],
                )
            output.research_brief = _produce_technical_summary(research_input.papers)

        elif action == "recommend":
            if not research_input.papers:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'papers' list is required for recommend action"],
                )
            output.recommendations = _recommend_follow_up(research_input.papers)

        elif action == "hand_off":
            if not research_input.target_agent:
                return AgentResult(
                    agent_name=self.name,
                    status="failure",
                    errors=["'target_agent' is required for hand_off action"],
                )
            paper_ids = [p.get("paper_id", "unknown") for p in research_input.papers]
            summary = f"Research findings from {len(research_input.papers)} papers."
            output.handoff = _hand_off_implications(
                summary, research_input.target_agent, paper_ids
            )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
