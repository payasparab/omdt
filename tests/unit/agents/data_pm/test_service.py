"""Tests for app.agents.data_pm.service — DataPMAgent PRD generation."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext
from app.agents.data_pm.schemas import DataPMInput, PRDDraftOutput
from app.agents.data_pm.service import DataPMAgent


@pytest.fixture
def agent() -> DataPMAgent:
    return DataPMAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(
            correlation_id="corr-pm-test",
            work_item_id="wi-456",
            input_data=input_data,
        )
    return _make


@pytest.fixture
def valid_inputs() -> dict:
    return {
        "work_item_id": "wi-456",
        "title": "Sales Dashboard",
        "description": "Build a real-time sales dashboard for the executive team",
        "route_key": "dashboard_request",
        "priority": "high",
        "requester": "payas.parab",
        "business_goal": "Track revenue in real time",
        "source_data": "Snowflake analytics schema",
    }


class TestDataPMExecution:
    @pytest.mark.asyncio
    async def test_successful_prd_generation(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        assert result.status == "success"
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert prd.prd_title.startswith("PRD:")
        assert prd.work_item_id == "wi-456"

    @pytest.mark.asyncio
    async def test_acceptance_criteria_generated(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert len(prd.acceptance_criteria) >= 3
        # With source_data provided, should have data validation criterion
        assert any("source data" in ac.description.lower() or "validated" in ac.description.lower()
                    for ac in prd.acceptance_criteria)

    @pytest.mark.asyncio
    async def test_milestones_generated(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert len(prd.milestones) >= 3
        milestone_names = [m.name for m in prd.milestones]
        assert "Requirements Finalized" in milestone_names

    @pytest.mark.asyncio
    async def test_risks_identified(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert len(prd.risks) >= 1
        for risk in prd.risks:
            assert risk.description
            assert risk.likelihood in ("low", "medium", "high")

    @pytest.mark.asyncio
    async def test_missing_source_data_adds_risk(
        self, agent: DataPMAgent, context_factory
    ) -> None:
        inputs = {
            "work_item_id": "wi-789",
            "title": "Mystery Project",
            "description": "Some vague request",
            "route_key": "analysis_request",
        }
        ctx = context_factory(inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert any("source data" in r.description.lower() for r in prd.risks)

    @pytest.mark.asyncio
    async def test_critical_priority_adds_risk(
        self, agent: DataPMAgent, context_factory
    ) -> None:
        inputs = {
            "work_item_id": "wi-urgent",
            "title": "Critical Fix",
            "description": "Must be done now",
            "route_key": "pipeline_request",
            "priority": "critical",
            "source_data": "production",
        }
        ctx = context_factory(inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert any("critical" in r.description.lower() for r in prd.risks)

    @pytest.mark.asyncio
    async def test_stakeholders_from_requester(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert "payas.parab" in prd.stakeholders

    @pytest.mark.asyncio
    async def test_handoff_to_technical_writer(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert prd.handoff_to == "technical_writer_agent"

    @pytest.mark.asyncio
    async def test_required_agents_from_route(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert "data_analyst" in prd.required_agents

    @pytest.mark.asyncio
    async def test_assumptions_populated(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        prd = PRDDraftOutput.model_validate(result.outputs)
        assert len(prd.assumptions) >= 2


class TestDataPMValidation:
    @pytest.mark.asyncio
    async def test_missing_required_inputs_fails(
        self, agent: DataPMAgent, context_factory
    ) -> None:
        ctx = context_factory({"work_item_id": "wi-1"})
        result = await agent.execute(ctx)
        assert result.status == "failure"
        assert any("title" in e or "description" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_output_validates_against_schema(
        self, agent: DataPMAgent, context_factory, valid_inputs: dict
    ) -> None:
        ctx = context_factory(valid_inputs)
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)


class TestDataPMAgentMeta:
    def test_name(self) -> None:
        assert DataPMAgent().name == "data_pm"

    def test_required_inputs(self) -> None:
        agent = DataPMAgent()
        assert "work_item_id" in agent.required_inputs
        assert "title" in agent.required_inputs
        assert "description" in agent.required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataPMAgent()
        targets = agent.get_handoff_targets()
        assert "technical_writer_agent" in targets
        assert "head_of_data" in targets
