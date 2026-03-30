"""Tests for app.agents.academic.service — AcademicResearchAgent."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult
from app.agents.academic.schemas import (
    AcademicResearchOutput,
    LiteratureMatrix,
    PaperMetadata,
    PaperSummary,
    ResearchBrief,
)
from app.agents.academic.service import AcademicResearchAgent


@pytest.fixture
def agent() -> AcademicResearchAgent:
    return AcademicResearchAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(
            correlation_id="corr-test",
            work_item_id="wi-123",
            input_data=input_data,
        )
    return _make


SAMPLE_PAPER = {
    "paper_id": "paper-001",
    "title": "Attention Is All You Need",
    "authors": ["Vaswani, A.", "Shazeer, N."],
    "year": 2017,
    "venue": "NeurIPS",
    "method": "Transformer architecture",
    "dataset": "WMT 2014",
    "metrics": ["BLEU"],
    "main_results": "State-of-the-art translation quality",
    "limitations": ["Quadratic attention complexity"],
    "assumptions": ["Large-scale parallel corpus available"],
    "results_summary": "28.4 BLEU on WMT EN-DE",
    "citations": ["BERT (Devlin 2019)", "GPT (Radford 2018)"],
}

SAMPLE_PAPER_2 = {
    "paper_id": "paper-002",
    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
    "authors": ["Devlin, J."],
    "year": 2019,
    "venue": "NAACL",
    "method": "Masked language modeling",
    "dataset": "BookCorpus + Wikipedia",
    "metrics": ["F1", "Accuracy"],
    "main_results": "State-of-the-art on 11 NLP tasks",
    "limitations": ["High compute requirements"],
    "citations": ["XLNet (Yang 2019)"],
}


# ---------------------------------------------------------------------------
# Paper metadata extraction
# ---------------------------------------------------------------------------

class TestParseMetadata:
    @pytest.mark.asyncio
    async def test_parse_metadata_from_text(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "parse_metadata", "source": "A Study on Transformers"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.paper_metadata is not None
        assert output.paper_metadata.title == "A Study on Transformers"

    @pytest.mark.asyncio
    async def test_parse_metadata_from_url(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "parse_metadata", "source": "https://arxiv.org/abs/1706.03762"})
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.paper_metadata is not None
        assert output.paper_metadata.url == "https://arxiv.org/abs/1706.03762"

    @pytest.mark.asyncio
    async def test_parse_metadata_generates_id(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "parse_metadata", "source": "Test Paper"})
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.paper_metadata is not None
        assert len(output.paper_metadata.paper_id) > 0

    @pytest.mark.asyncio
    async def test_parse_metadata_requires_source(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "parse_metadata"})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("source" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Paper summary
# ---------------------------------------------------------------------------

class TestPaperSummary:
    @pytest.mark.asyncio
    async def test_summary_follows_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "summarize", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.paper_summary is not None
        summary = output.paper_summary
        # Verify all PaperSummary fields
        assert summary.paper_id == "paper-001"
        assert summary.title == "Attention Is All You Need"
        assert len(summary.problem_statement) > 0
        assert len(summary.method_summary) > 0
        assert isinstance(summary.datasets, list)
        assert isinstance(summary.metrics, list)
        assert isinstance(summary.limitations, list)
        assert isinstance(summary.citations, list)

    @pytest.mark.asyncio
    async def test_summary_preserves_paper_data(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "summarize", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        summary = output.paper_summary
        assert summary.datasets == ["WMT 2014"]
        assert summary.metrics == ["BLEU"]
        assert "Quadratic attention complexity" in summary.limitations
        assert "BERT (Devlin 2019)" in summary.citations

    @pytest.mark.asyncio
    async def test_summary_requires_papers(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "summarize", "papers": []})
        result = await agent.execute(ctx)
        assert result.status == "failure"


# ---------------------------------------------------------------------------
# Literature comparison matrix
# ---------------------------------------------------------------------------

class TestLiteratureMatrix:
    @pytest.mark.asyncio
    async def test_compare_two_papers(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "compare",
            "papers": [SAMPLE_PAPER, SAMPLE_PAPER_2],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        matrix = output.literature_matrix
        assert matrix is not None
        assert len(matrix.papers) == 2
        assert len(matrix.comparison_dimensions) > 0
        assert "paper-001" in matrix.matrix_data
        assert "paper-002" in matrix.matrix_data

    @pytest.mark.asyncio
    async def test_compare_requires_at_least_two(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "compare", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("2 papers" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_matrix_dimensions_cover_key_aspects(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "compare",
            "papers": [SAMPLE_PAPER, SAMPLE_PAPER_2],
        })
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        dims = output.literature_matrix.comparison_dimensions
        assert "method" in dims
        assert "dataset" in dims
        assert "metrics" in dims


# ---------------------------------------------------------------------------
# Executive vs technical summary differentiation
# ---------------------------------------------------------------------------

class TestSummaryDifferentiation:
    @pytest.mark.asyncio
    async def test_executive_summary(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "executive_summary",
            "papers": [SAMPLE_PAPER, SAMPLE_PAPER_2],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        brief = output.research_brief
        assert brief is not None
        assert brief.summary_type == "executive"
        assert len(brief.synthesis) > 0
        assert len(brief.recommendations) > 0

    @pytest.mark.asyncio
    async def test_technical_summary(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "technical_summary",
            "papers": [SAMPLE_PAPER, SAMPLE_PAPER_2],
        })
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        brief = output.research_brief
        assert brief is not None
        assert brief.summary_type == "technical"
        assert len(brief.synthesis) > 0

    @pytest.mark.asyncio
    async def test_executive_and_technical_differ(self, agent, context_factory) -> None:
        papers = [SAMPLE_PAPER, SAMPLE_PAPER_2]
        ctx_exec = context_factory({"action": "executive_summary", "papers": papers})
        ctx_tech = context_factory({"action": "technical_summary", "papers": papers})
        exec_result = await agent.execute(ctx_exec)
        tech_result = await agent.execute(ctx_tech)
        exec_brief = AcademicResearchOutput.model_validate(exec_result.outputs).research_brief
        tech_brief = AcademicResearchOutput.model_validate(tech_result.outputs).research_brief
        assert exec_brief.summary_type != tech_brief.summary_type
        assert exec_brief.synthesis != tech_brief.synthesis


# ---------------------------------------------------------------------------
# Handoff to target agent
# ---------------------------------------------------------------------------

class TestHandoff:
    @pytest.mark.asyncio
    async def test_handoff_to_data_scientist(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "hand_off",
            "papers": [SAMPLE_PAPER],
            "target_agent": "data_scientist",
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.handoff is not None
        assert output.handoff.target_agent == "data_scientist"
        assert len(output.handoff.actionable_items) > 0
        assert "paper-001" in output.handoff.source_paper_ids

    @pytest.mark.asyncio
    async def test_handoff_to_data_pm(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "hand_off",
            "papers": [SAMPLE_PAPER],
            "target_agent": "data_pm",
        })
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.handoff.target_agent == "data_pm"

    @pytest.mark.asyncio
    async def test_handoff_requires_target_agent(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "hand_off", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("target_agent" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Methodology extraction
# ---------------------------------------------------------------------------

class TestMethodology:
    @pytest.mark.asyncio
    async def test_methodology_extraction(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "methodology", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.methodology is not None
        assert output.methodology.method == "Transformer architecture"
        assert output.methodology.dataset == "WMT 2014"


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    @pytest.mark.asyncio
    async def test_recommend_follow_up(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "recommend", "papers": [SAMPLE_PAPER]})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        assert len(output.recommendations) > 0


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------

class TestAcademicAgentMeta:
    def test_name(self) -> None:
        assert AcademicResearchAgent().name == "academic_research_agent"

    def test_required_inputs(self) -> None:
        assert "action" in AcademicResearchAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = AcademicResearchAgent()
        assert "data_scientist" in agent.get_handoff_targets()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_invalid_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "invalid_action"})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("Unknown action" in e for e in result.errors)
