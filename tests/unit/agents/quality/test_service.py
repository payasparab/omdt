"""Tests for app.agents.quality.service — DataQualityAgent."""
from __future__ import annotations

import pytest

from app.agents.quality.service import DataQualityAgent, DataQualityOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DataQualityAgent:
    return DataQualityAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDataQualityAgent:
    def test_name(self) -> None:
        assert DataQualityAgent().name == "quality_agent"

    def test_required_inputs(self) -> None:
        assert "quality_request" in DataQualityAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataQualityAgent()
        assert "data_engineer" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_quality_rules(self, agent, context_factory) -> None:
        ctx = context_factory({"quality_request": "Check users table", "tables": ["users"]})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DataQualityOutput.model_validate(result.outputs)
        assert len(output.quality_rules) >= 2
        rule_types = {r.rule_type for r in output.quality_rules}
        assert "not_null" in rule_types
        assert "unique" in rule_types

    @pytest.mark.asyncio
    async def test_produces_quality_tests(self, agent, context_factory) -> None:
        ctx = context_factory({"quality_request": "Test orders", "tables": ["orders"]})
        result = await agent.execute(ctx)
        output = DataQualityOutput.model_validate(result.outputs)
        assert len(output.quality_tests) >= 2
        assert all(t.query != "" for t in output.quality_tests)

    @pytest.mark.asyncio
    async def test_produces_validation_report(self, agent, context_factory) -> None:
        ctx = context_factory({"quality_request": "Validate pipeline", "pipeline_key": "etl_users"})
        result = await agent.execute(ctx)
        output = DataQualityOutput.model_validate(result.outputs)
        assert output.validation_report is not None
        assert output.validation_report.pipeline_key == "etl_users"
        assert output.validation_report.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_tables(self, agent, context_factory) -> None:
        ctx = context_factory({"quality_request": "Check all", "tables": ["users", "orders", "products"]})
        result = await agent.execute(ctx)
        output = DataQualityOutput.model_validate(result.outputs)
        assert len(output.quality_rules) >= 6  # 2 per table

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"quality_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
