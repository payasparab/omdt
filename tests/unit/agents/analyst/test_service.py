"""Tests for app.agents.analyst.service — DataAnalystAgent."""
from __future__ import annotations

import pytest

from app.agents.analyst.service import DataAnalystAgent, DataAnalystOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DataAnalystAgent:
    return DataAnalystAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDataAnalystAgent:
    def test_name(self) -> None:
        assert DataAnalystAgent().name == "data_analyst"

    def test_required_inputs(self) -> None:
        assert "analysis_request" in DataAnalystAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataAnalystAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_memo_output(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "Revenue analysis", "output_format": "memo"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DataAnalystOutput.model_validate(result.outputs)
        assert output.analysis_memo is not None
        assert "Revenue" in output.analysis_memo.title

    @pytest.mark.asyncio
    async def test_query_package_output(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "Revenue analysis", "output_format": "query_package"})
        result = await agent.execute(ctx)
        output = DataAnalystOutput.model_validate(result.outputs)
        assert output.query_package is not None
        assert len(output.query_package.queries) > 0

    @pytest.mark.asyncio
    async def test_dashboard_spec_output(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "KPI dashboard", "output_format": "dashboard_spec"})
        result = await agent.execute(ctx)
        output = DataAnalystOutput.model_validate(result.outputs)
        assert output.dashboard_spec is not None
        assert len(output.dashboard_spec.charts) > 0

    @pytest.mark.asyncio
    async def test_full_output(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "Full analysis", "output_format": "full"})
        result = await agent.execute(ctx)
        output = DataAnalystOutput.model_validate(result.outputs)
        assert output.analysis_memo is not None
        assert output.query_package is not None
        assert output.dashboard_spec is not None

    @pytest.mark.asyncio
    async def test_invalid_format_fails(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "Test", "output_format": "invalid"})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"analysis_request": "Test", "output_format": "full"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
