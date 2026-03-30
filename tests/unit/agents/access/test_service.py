"""Tests for app.agents.access.service — AccessSecurityAgent."""
from __future__ import annotations

import pytest

from app.agents.access.service import AccessSecurityAgent, AccessSecurityOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> AccessSecurityAgent:
    return AccessSecurityAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestAccessSecurityAgent:
    def test_name(self) -> None:
        assert AccessSecurityAgent().name == "access_security_agent"

    def test_required_inputs(self) -> None:
        assert "access_request" in AccessSecurityAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = AccessSecurityAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_access_package(self, agent, context_factory) -> None:
        ctx = context_factory({
            "access_request": "Need Snowflake read access",
            "requester": "analyst@example.com",
            "role_bundle": "analyst_read",
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = AccessSecurityOutput.model_validate(result.outputs)
        assert output.access_package is not None
        assert output.access_package.role_bundle == "analyst_read"
        assert output.access_package.requires_approval is True

    @pytest.mark.asyncio
    async def test_produces_provisioning_steps(self, agent, context_factory) -> None:
        ctx = context_factory({
            "access_request": "Grant access",
            "requester": "user@example.com",
            "role_bundle": "admin_write",
        })
        result = await agent.execute(ctx)
        output = AccessSecurityOutput.model_validate(result.outputs)
        assert len(output.provisioning_steps) >= 4
        actions = [s.action for s in output.provisioning_steps]
        assert "validate_policy" in actions
        assert "grant_role" in actions
        assert "verify_access" in actions

    @pytest.mark.asyncio
    async def test_steps_are_ordered(self, agent, context_factory) -> None:
        ctx = context_factory({"access_request": "Access", "requester": "u@ex.com"})
        result = await agent.execute(ctx)
        output = AccessSecurityOutput.model_validate(result.outputs)
        orders = [s.order for s in output.provisioning_steps]
        assert orders == sorted(orders)

    @pytest.mark.asyncio
    async def test_read_role_low_risk(self, agent, context_factory) -> None:
        ctx = context_factory({"access_request": "Need read", "role_bundle": "analyst_read"})
        result = await agent.execute(ctx)
        output = AccessSecurityOutput.model_validate(result.outputs)
        assert output.access_package.risk_assessment == "low"

    @pytest.mark.asyncio
    async def test_write_role_medium_risk(self, agent, context_factory) -> None:
        ctx = context_factory({"access_request": "Need write", "role_bundle": "admin_write"})
        result = await agent.execute(ctx)
        output = AccessSecurityOutput.model_validate(result.outputs)
        assert output.access_package.risk_assessment == "medium"

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"access_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
