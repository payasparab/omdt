"""Tests for app.agents.vendor.service — VendorFinOpsAgent."""
from __future__ import annotations

import pytest

from app.agents.vendor.service import VendorFinOpsAgent, VendorFinOpsOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> VendorFinOpsAgent:
    return VendorFinOpsAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestVendorFinOpsAgent:
    def test_name(self) -> None:
        assert VendorFinOpsAgent().name == "vendor_finops_agent"

    def test_required_inputs(self) -> None:
        assert "vendor_request" in VendorFinOpsAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = VendorFinOpsAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_vendor_brief(self, agent, context_factory) -> None:
        ctx = context_factory({"vendor_request": "Evaluate Snowflake", "vendor_name": "Snowflake"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = VendorFinOpsOutput.model_validate(result.outputs)
        assert output.vendor_brief is not None
        assert output.vendor_brief.vendor_name == "Snowflake"

    @pytest.mark.asyncio
    async def test_produces_cost_summary(self, agent, context_factory) -> None:
        ctx = context_factory({"vendor_request": "Cost review", "vendor_name": "AWS", "budget": 120000.0})
        result = await agent.execute(ctx)
        output = VendorFinOpsOutput.model_validate(result.outputs)
        assert output.cost_summary is not None
        assert output.cost_summary.annual_cost == 120000.0
        assert output.cost_summary.monthly_cost == 10000.0

    @pytest.mark.asyncio
    async def test_produces_renewal_task(self, agent, context_factory) -> None:
        ctx = context_factory({"vendor_request": "Renewal review", "vendor_name": "Databricks"})
        result = await agent.execute(ctx)
        output = VendorFinOpsOutput.model_validate(result.outputs)
        assert output.renewal_task is not None
        assert output.renewal_task.vendor_name == "Databricks"
        assert output.renewal_task.requires_approval is True

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"vendor_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
