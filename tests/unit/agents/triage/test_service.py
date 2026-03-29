"""Tests for app.agents.triage.service — TriageAgent classification and routing."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult
from app.agents.triage.schemas import (
    REQUIRED_CLARIFICATION_FIELDS,
    TriageInput,
    TriageOutput,
)
from app.agents.triage.service import TriageAgent
from app.domain.enums import CanonicalState, Priority, WorkItemType


@pytest.fixture
def agent() -> TriageAgent:
    return TriageAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(
            correlation_id="corr-test",
            work_item_id="wi-123",
            input_data=input_data,
        )
    return _make


# ---------------------------------------------------------------------------
# Route classification tests
# ---------------------------------------------------------------------------

class TestTriageRouting:
    @pytest.mark.asyncio
    async def test_analysis_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "I need an analysis of our sales metrics"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "analysis_request"

    @pytest.mark.asyncio
    async def test_dashboard_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build me a dashboard for visualizing revenue"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "dashboard_request"

    @pytest.mark.asyncio
    async def test_pipeline_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Need a new ETL pipeline for ingestion from S3"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "pipeline_request"

    @pytest.mark.asyncio
    async def test_data_model_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Design a new data model schema for the entity table"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "data_model_request"

    @pytest.mark.asyncio
    async def test_data_science_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build a machine learning model to predict churn"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "data_science_request"

    @pytest.mark.asyncio
    async def test_paper_review_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Review this research paper on academic literature"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "paper_review_request"

    @pytest.mark.asyncio
    async def test_documentation_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Create a runbook document for the deployment process"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "documentation_request"

    @pytest.mark.asyncio
    async def test_training_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "We need onboarding training for the new hire"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "training_request"

    @pytest.mark.asyncio
    async def test_access_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Grant access permission to the Snowflake role"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "access_request"

    @pytest.mark.asyncio
    async def test_bug_or_incident(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "There is a bug causing an error in production"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "bug_or_incident"

    @pytest.mark.asyncio
    async def test_vendor_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Need to evaluate a new vendor for our license costs"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "vendor_or_procurement"

    @pytest.mark.asyncio
    async def test_status_request(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Can I get a status update on the weekly progress?"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "status_or_reporting"

    @pytest.mark.asyncio
    async def test_unknown_request_defaults(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Hello there, just wanted to check in."})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.route_key == "unknown_needs_clarification"
        assert output.confidence < 0.6


# ---------------------------------------------------------------------------
# Clarification detection tests
# ---------------------------------------------------------------------------

class TestTriageClarification:
    @pytest.mark.asyncio
    async def test_missing_fields_detected(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build a dashboard"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        # Without any clarification fields, all 8 should be missing
        assert len(output.missing_info_checklist) == len(REQUIRED_CLARIFICATION_FIELDS)

    @pytest.mark.asyncio
    async def test_provided_fields_reduce_missing(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({
            "message_body": "Build a dashboard",
            "business_goal": "Track revenue",
            "urgency": "high",
        })
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert "business_goal" not in output.missing_info_checklist
        assert "urgency" not in output.missing_info_checklist
        assert len(output.missing_info_checklist) == 6

    @pytest.mark.asyncio
    async def test_max_three_questions_per_round(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Do something"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert len(output.clarification_questions) <= 3

    @pytest.mark.asyncio
    async def test_questions_reference_missing_fields(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Analyze data"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        question_fields = {q.field_name for q in output.clarification_questions}
        for field in question_fields:
            assert field in output.missing_info_checklist

    @pytest.mark.asyncio
    async def test_needs_clarification_state_when_missing(
        self, agent: TriageAgent, context_factory
    ) -> None:
        ctx = context_factory({"message_body": "Do something"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.recommended_next_state == CanonicalState.NEEDS_CLARIFICATION

    @pytest.mark.asyncio
    async def test_ready_for_prd_when_all_present(
        self, agent: TriageAgent, context_factory
    ) -> None:
        full_inputs = {"message_body": "Build analysis dashboard"}
        for field in REQUIRED_CLARIFICATION_FIELDS:
            full_inputs[field] = "provided"
        ctx = context_factory(full_inputs)
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.recommended_next_state == CanonicalState.READY_FOR_PRD
        assert output.missing_info_checklist == []


# ---------------------------------------------------------------------------
# Priority and output tests
# ---------------------------------------------------------------------------

class TestTriagePriority:
    @pytest.mark.asyncio
    async def test_critical_keywords(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "URGENT: production outage emergency"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.priority == Priority.CRITICAL

    @pytest.mark.asyncio
    async def test_low_priority_keywords(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Low priority nice to have backlog item"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_default_medium_priority(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build a new pipeline for data"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.priority == Priority.MEDIUM


class TestTriageOutput:
    @pytest.mark.asyncio
    async def test_output_schema_valid(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Analyze our sales data metrics"})
        result = await agent.execute(ctx)
        # Should validate without errors
        output = TriageOutput.model_validate(result.outputs)
        assert isinstance(output.normalized_title, str)
        assert isinstance(output.work_item_type, WorkItemType)
        assert isinstance(output.confidence, float)
        assert 0.0 <= output.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_normalized_title_from_subject(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({
            "message_body": "Details here",
            "subject": "Sales Dashboard Request",
        })
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.normalized_title == "Sales Dashboard Request"

    @pytest.mark.asyncio
    async def test_normalized_title_from_body(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build me a pipeline\nMore details here"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.normalized_title == "Build me a pipeline"

    @pytest.mark.asyncio
    async def test_missing_message_body_fails(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("message_body" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_linear_sync_intent_default_true(
        self, agent: TriageAgent, context_factory
    ) -> None:
        ctx = context_factory({"message_body": "Create a report"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert output.linear_sync_intent is True

    @pytest.mark.asyncio
    async def test_required_agents_populated(self, agent: TriageAgent, context_factory) -> None:
        ctx = context_factory({"message_body": "Build an analysis of our data metrics"})
        result = await agent.execute(ctx)
        output = TriageOutput.model_validate(result.outputs)
        assert len(output.required_agents) > 0


# ---------------------------------------------------------------------------
# Agent metadata tests
# ---------------------------------------------------------------------------

class TestTriageAgentMeta:
    def test_name(self) -> None:
        assert TriageAgent().name == "triage_agent"

    def test_required_inputs(self) -> None:
        assert "message_body" in TriageAgent().required_inputs

    def test_allowed_tools(self) -> None:
        agent = TriageAgent()
        assert "create_draft_work_item" in agent.allowed_tools
        assert "ask_clarification" in agent.allowed_tools

    def test_handoff_targets(self) -> None:
        agent = TriageAgent()
        assert "data_pm" in agent.get_handoff_targets()
        assert "head_of_data" in agent.get_handoff_targets()
