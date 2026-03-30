"""Snapshot tests for agent output fixtures — verify output structure stability."""
from __future__ import annotations

import json

import pytest

from app.agents.base import AgentContext
from app.agents.academic.schemas import AcademicResearchOutput, PaperSummary
from app.agents.academic.service import AcademicResearchAgent
from app.agents.technical_writer.schemas import DocumentOutput, TechnicalWriterOutput
from app.agents.technical_writer.service import TechnicalWriterAgent
from app.agents.training_enablement.schemas import (
    TrainingEnablementOutput,
    TrainingPlan,
)
from app.agents.training_enablement.service import TrainingEnablementAgent


def _ctx(input_data: dict) -> AgentContext:
    return AgentContext(
        correlation_id="corr-snapshot",
        work_item_id="wi-snap",
        input_data=input_data,
    )


# ---------------------------------------------------------------------------
# Paper summary fixture snapshot
# ---------------------------------------------------------------------------

PAPER_FIXTURE = {
    "paper_id": "snap-paper-001",
    "title": "Snapshot Test Paper",
    "authors": ["Author A", "Author B"],
    "year": 2024,
    "venue": "ICML",
    "method": "Novel approach",
    "dataset": "ImageNet",
    "metrics": ["Top-1 Accuracy", "Top-5 Accuracy"],
    "main_results": "92% top-1 accuracy",
    "limitations": ["Limited to image classification"],
    "threats_to_validity": ["Single dataset evaluation"],
    "relevance_to_omdt_project": "Potential application in data quality scoring",
    "recommended_next_steps": ["Evaluate on tabular data"],
    "citations": ["ResNet (He 2015)", "ViT (Dosovitskiy 2020)"],
}


class TestPaperSummarySnapshot:
    @pytest.mark.asyncio
    async def test_paper_summary_structure(self) -> None:
        agent = AcademicResearchAgent()
        result = await agent.execute(_ctx({
            "action": "summarize",
            "papers": [PAPER_FIXTURE],
        }))
        assert result.status == "success"
        output = AcademicResearchOutput.model_validate(result.outputs)
        summary = output.paper_summary

        # Snapshot: verify structure has all expected keys
        snapshot_keys = {
            "paper_id", "title", "problem_statement", "method_summary",
            "datasets", "metrics", "main_results", "limitations",
            "threats_to_validity", "relevance_to_omdt_project",
            "recommended_next_steps", "citations",
        }
        actual_keys = set(summary.model_dump().keys())
        assert snapshot_keys == actual_keys

    @pytest.mark.asyncio
    async def test_paper_summary_fixture_values(self) -> None:
        agent = AcademicResearchAgent()
        result = await agent.execute(_ctx({
            "action": "summarize",
            "papers": [PAPER_FIXTURE],
        }))
        output = AcademicResearchOutput.model_validate(result.outputs)
        summary = output.paper_summary

        # Snapshot: verify fixture data is preserved
        assert summary.paper_id == "snap-paper-001"
        assert summary.title == "Snapshot Test Paper"
        assert summary.datasets == ["ImageNet"]
        assert summary.metrics == ["Top-1 Accuracy", "Top-5 Accuracy"]
        assert summary.main_results == "92% top-1 accuracy"

    @pytest.mark.asyncio
    async def test_paper_summary_serializes_to_json(self) -> None:
        agent = AcademicResearchAgent()
        result = await agent.execute(_ctx({
            "action": "summarize",
            "papers": [PAPER_FIXTURE],
        }))
        output = AcademicResearchOutput.model_validate(result.outputs)
        # Should round-trip through JSON cleanly
        json_str = json.dumps(output.model_dump(), default=str)
        parsed = json.loads(json_str)
        assert parsed["paper_summary"]["paper_id"] == "snap-paper-001"


# ---------------------------------------------------------------------------
# Technical writer output fixture snapshot
# ---------------------------------------------------------------------------

class TestTechnicalWriterOutputSnapshot:
    @pytest.mark.asyncio
    async def test_technical_memo_structure(self) -> None:
        agent = TechnicalWriterAgent()
        result = await agent.execute(_ctx({
            "action": "technical_memo",
            "source_artifacts": ["snap-art-1", "snap-art-2"],
            "audience": "technical",
            "title": "Snapshot Technical Memo",
        }))
        assert result.status == "success"
        output = TechnicalWriterOutput.model_validate(result.outputs)
        doc = output.document

        # Snapshot: verify DocumentOutput has all expected keys
        snapshot_keys = {
            "document_id", "document_type", "audience", "title",
            "executive_summary", "source_artifacts",
            "key_changes_or_findings", "prerequisites",
            "procedure_or_narrative", "risks_and_caveats",
            "glossary", "reviewers", "publication_targets",
        }
        actual_keys = set(doc.model_dump().keys())
        assert snapshot_keys == actual_keys

    @pytest.mark.asyncio
    async def test_technical_memo_fixture_values(self) -> None:
        agent = TechnicalWriterAgent()
        result = await agent.execute(_ctx({
            "action": "technical_memo",
            "source_artifacts": ["snap-art-1", "snap-art-2"],
            "audience": "technical",
            "title": "Snapshot Technical Memo",
        }))
        output = TechnicalWriterOutput.model_validate(result.outputs)
        doc = output.document

        assert doc.document_type == "technical_memo"
        assert doc.audience == "technical"
        assert doc.title == "Snapshot Technical Memo"
        assert doc.source_artifacts == ["snap-art-1", "snap-art-2"]
        assert len(doc.glossary) > 0

    @pytest.mark.asyncio
    async def test_technical_memo_serializes_to_json(self) -> None:
        agent = TechnicalWriterAgent()
        result = await agent.execute(_ctx({
            "action": "technical_memo",
            "source_artifacts": ["snap-art-1"],
            "title": "JSON Test",
        }))
        output = TechnicalWriterOutput.model_validate(result.outputs)
        json_str = json.dumps(output.model_dump(), default=str)
        parsed = json.loads(json_str)
        assert parsed["document"]["document_type"] == "technical_memo"


# ---------------------------------------------------------------------------
# Training plan fixture snapshot
# ---------------------------------------------------------------------------

class TestTrainingPlanSnapshot:
    @pytest.mark.asyncio
    async def test_training_plan_structure(self) -> None:
        agent = TrainingEnablementAgent()
        result = await agent.execute(_ctx({
            "action": "onboarding_plan",
            "audience_role": "data_analyst",
            "tool_scope": ["snowflake", "looker"],
        }))
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        plan = output.training_plan

        # Snapshot: verify TrainingPlan has all expected keys
        snapshot_keys = {
            "training_plan_id", "audience_role", "tool_scope",
            "learning_objectives", "prerequisites", "onboarding_steps",
            "exercises", "knowledge_checks", "artifacts",
            "completion_criteria", "follow_up_actions",
        }
        actual_keys = set(plan.model_dump().keys())
        assert snapshot_keys == actual_keys

    @pytest.mark.asyncio
    async def test_training_plan_fixture_values(self) -> None:
        agent = TrainingEnablementAgent()
        result = await agent.execute(_ctx({
            "action": "onboarding_plan",
            "audience_role": "data_analyst",
            "tool_scope": ["snowflake", "looker"],
        }))
        output = TrainingEnablementOutput.model_validate(result.outputs)
        plan = output.training_plan

        assert plan.audience_role == "data_analyst"
        assert plan.tool_scope == ["snowflake", "looker"]
        assert len(plan.learning_objectives) > 0
        assert len(plan.onboarding_steps) > 0
        assert len(plan.completion_criteria) > 0

    @pytest.mark.asyncio
    async def test_training_plan_serializes_to_json(self) -> None:
        agent = TrainingEnablementAgent()
        result = await agent.execute(_ctx({
            "action": "onboarding_plan",
            "audience_role": "data_engineer",
            "tool_scope": ["dbt"],
        }))
        output = TrainingEnablementOutput.model_validate(result.outputs)
        json_str = json.dumps(output.model_dump(), default=str)
        parsed = json.loads(json_str)
        assert parsed["training_plan"]["audience_role"] == "data_engineer"
