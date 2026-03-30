"""Tests for app.agents.engineer.service — DataEngineerAgent."""
from __future__ import annotations

import pytest

from app.agents.engineer.service import DataEngineerAgent, DataEngineerOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DataEngineerAgent:
    return DataEngineerAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDataEngineerAgent:
    def test_name(self) -> None:
        assert DataEngineerAgent().name == "data_engineer"

    def test_required_inputs(self) -> None:
        assert "pipeline_request" in DataEngineerAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataEngineerAgent()
        assert "data_architect" in agent.get_handoff_targets()
        assert "deployment_agent" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_pipeline_spec(self, agent, context_factory) -> None:
        ctx = context_factory({"pipeline_request": "ETL pipeline for user events"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DataEngineerOutput.model_validate(result.outputs)
        assert output.pipeline_spec is not None
        assert output.pipeline_spec.pipeline_type == "sql_transformation"

    @pytest.mark.asyncio
    async def test_produces_jobs(self, agent, context_factory) -> None:
        ctx = context_factory({"pipeline_request": "Build ingestion pipeline"})
        result = await agent.execute(ctx)
        output = DataEngineerOutput.model_validate(result.outputs)
        assert len(output.jobs) >= 3
        job_names = [j.job_name for j in output.jobs]
        assert "extract" in job_names
        assert "transform" in job_names
        assert "load" in job_names

    @pytest.mark.asyncio
    async def test_produces_transforms(self, agent, context_factory) -> None:
        ctx = context_factory({"pipeline_request": "Transform user data"})
        result = await agent.execute(ctx)
        output = DataEngineerOutput.model_validate(result.outputs)
        assert len(output.transforms) > 0

    @pytest.mark.asyncio
    async def test_custom_source_tables(self, agent, context_factory) -> None:
        ctx = context_factory({
            "pipeline_request": "Custom pipeline",
            "source_tables": ["raw.events", "raw.users"],
            "target_tables": ["analytics.user_events"],
        })
        result = await agent.execute(ctx)
        output = DataEngineerOutput.model_validate(result.outputs)
        assert output.pipeline_spec.source_tables == ["raw.events", "raw.users"]
        assert output.pipeline_spec.target_tables == ["analytics.user_events"]

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"pipeline_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
