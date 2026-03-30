"""Tests for app.agents.technical_writer.service — TechnicalWriterAgent."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult
from app.agents.technical_writer.schemas import (
    DocumentOutput,
    MissingFact,
    ReviewChecklistItem,
    TechnicalWriterOutput,
)
from app.agents.technical_writer.service import TechnicalWriterAgent


@pytest.fixture
def agent() -> TechnicalWriterAgent:
    return TechnicalWriterAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(
            correlation_id="corr-test",
            work_item_id="wi-456",
            input_data=input_data,
        )
    return _make


# ---------------------------------------------------------------------------
# Document type generation tests
# ---------------------------------------------------------------------------

class TestDocumentGeneration:
    @pytest.mark.asyncio
    async def test_executive_summary(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "executive_summary",
            "source_artifacts": ["art-1", "art-2"],
            "audience": "executive",
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document is not None
        assert output.document.document_type == "executive_summary"
        assert output.document.audience == "executive"

    @pytest.mark.asyncio
    async def test_technical_memo(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "technical_memo",
            "source_artifacts": ["art-1"],
            "audience": "technical",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.document_type == "technical_memo"
        assert len(output.document.glossary) > 0

    @pytest.mark.asyncio
    async def test_runbook(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "runbook",
            "source_artifacts": ["art-1"],
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.document_type == "runbook"
        assert output.document.audience == "operational"
        assert len(output.document.prerequisites) > 0

    @pytest.mark.asyncio
    async def test_release_notes(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "release_notes",
            "deployment_record": {"version": "2.1.0", "environment": "production"},
            "changes": ["Added new dashboard", "Fixed data refresh bug"],
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.document_type == "release_notes"
        assert "2.1.0" in output.document.title
        assert len(output.document.key_changes_or_findings) == 2

    @pytest.mark.asyncio
    async def test_sop(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "sop",
            "process_description": "Monthly data reconciliation process.",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.document_type == "sop"
        assert "reconciliation" in output.document.procedure_or_narrative

    @pytest.mark.asyncio
    async def test_user_guide(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "user_guide",
            "feature": "Dashboard Builder",
            "audience": "end_user",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.document_type == "user_guide"
        assert "Dashboard Builder" in output.document.title


# ---------------------------------------------------------------------------
# Missing facts detection
# ---------------------------------------------------------------------------

class TestMissingFactsDetection:
    @pytest.mark.asyncio
    async def test_detect_missing_with_no_artifacts(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "detect_missing", "source_artifacts": []})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert len(output.missing_facts) > 0
        assert any(mf.field == "source_artifacts" for mf in output.missing_facts)

    @pytest.mark.asyncio
    async def test_detect_missing_returns_clarification_not_assumption(
        self, agent, context_factory
    ) -> None:
        ctx = context_factory({"action": "detect_missing", "source_artifacts": ["art-1"]})
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        # Should ask a question, not fill in assumed data
        for mf in output.missing_facts:
            assert len(mf.question) > 0

    @pytest.mark.asyncio
    async def test_detect_missing_is_not_document(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "detect_missing", "source_artifacts": ["art-1"]})
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document is None  # Should not generate a document


# ---------------------------------------------------------------------------
# Source artifact citation
# ---------------------------------------------------------------------------

class TestSourceCitation:
    @pytest.mark.asyncio
    async def test_source_artifacts_in_output(self, agent, context_factory) -> None:
        artifacts = ["art-100", "art-200", "art-300"]
        ctx = context_factory({
            "action": "technical_memo",
            "source_artifacts": artifacts,
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.source_artifacts == artifacts


# ---------------------------------------------------------------------------
# Audience-appropriate tone
# ---------------------------------------------------------------------------

class TestAudienceTone:
    @pytest.mark.asyncio
    async def test_executive_tone(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "executive_summary",
            "source_artifacts": ["art-1"],
            "audience": "executive",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        # Executive summaries should mention business-oriented tone
        assert "executive" in output.document.audience

    @pytest.mark.asyncio
    async def test_end_user_tone(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "user_guide",
            "feature": "Reporting",
            "audience": "end_user",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.audience == "end_user"

    @pytest.mark.asyncio
    async def test_operational_tone_for_runbook(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "runbook", "source_artifacts": ["art-1"]})
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert output.document.audience == "operational"


# ---------------------------------------------------------------------------
# Output matches DocumentOutput schema
# ---------------------------------------------------------------------------

class TestOutputSchema:
    @pytest.mark.asyncio
    async def test_document_output_validates(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "technical_memo",
            "source_artifacts": ["art-1"],
            "title": "Test Memo",
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        doc = output.document
        # Validate all DocumentOutput fields exist
        assert isinstance(doc.document_id, str)
        assert len(doc.document_id) > 0
        assert isinstance(doc.document_type, str)
        assert isinstance(doc.audience, str)
        assert isinstance(doc.title, str)
        assert isinstance(doc.executive_summary, str)
        assert isinstance(doc.source_artifacts, list)
        assert isinstance(doc.key_changes_or_findings, list)
        assert isinstance(doc.prerequisites, list)
        assert isinstance(doc.procedure_or_narrative, str)
        assert isinstance(doc.risks_and_caveats, list)
        assert isinstance(doc.glossary, dict)
        assert isinstance(doc.reviewers, list)
        assert isinstance(doc.publication_targets, list)


# ---------------------------------------------------------------------------
# Review checklist
# ---------------------------------------------------------------------------

class TestReviewChecklist:
    @pytest.mark.asyncio
    async def test_review_checklist_generation(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "review_checklist",
            "document": {
                "title": "My Document",
                "executive_summary": "Summary here",
                "source_artifacts": ["art-1"],
            },
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        assert len(output.review_checklist) > 0
        assert all(isinstance(item, ReviewChecklistItem) for item in output.review_checklist)

    @pytest.mark.asyncio
    async def test_review_checklist_marks_present_fields(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "review_checklist",
            "document": {
                "title": "Filled Title",
                "executive_summary": "Filled Summary",
                "source_artifacts": ["art-1"],
            },
        })
        result = await agent.execute(ctx)
        output = TechnicalWriterOutput.model_validate(result.outputs)
        checked = [item for item in output.review_checklist if item.checked]
        assert len(checked) > 0


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------

class TestTechnicalWriterMeta:
    def test_name(self) -> None:
        assert TechnicalWriterAgent().name == "technical_writer_agent"

    def test_required_inputs(self) -> None:
        assert "action" in TechnicalWriterAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = TechnicalWriterAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_invalid_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "nonexistent"})
        result = await agent.execute(ctx)
        assert result.status == "failure"
