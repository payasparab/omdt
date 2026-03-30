"""Tests for app.agents.deployment.service — DeploymentAgent."""
from __future__ import annotations

import pytest

from app.agents.deployment.service import DeploymentAgent, DeploymentAgentOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DeploymentAgent:
    return DeploymentAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDeploymentAgent:
    def test_name(self) -> None:
        assert DeploymentAgent().name == "deployment_agent"

    def test_required_inputs(self) -> None:
        assert "deployment_request" in DeploymentAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DeploymentAgent()
        assert "data_engineer" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_release_plan(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Deploy v2.0", "environment": "staging"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DeploymentAgentOutput.model_validate(result.outputs)
        assert output.release_plan is not None
        assert output.release_plan.environment == "staging"
        assert len(output.release_plan.steps) > 0

    @pytest.mark.asyncio
    async def test_produces_deploy_record(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Deploy", "git_sha": "abc123"})
        result = await agent.execute(ctx)
        output = DeploymentAgentOutput.model_validate(result.outputs)
        assert output.deploy_record is not None
        assert output.deploy_record.git_sha == "abc123"

    @pytest.mark.asyncio
    async def test_produces_rollback_plan(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Deploy with rollback"})
        result = await agent.execute(ctx)
        output = DeploymentAgentOutput.model_validate(result.outputs)
        assert output.rollback_plan is not None
        assert len(output.rollback_plan.rollback_steps) > 0

    @pytest.mark.asyncio
    async def test_production_requires_approval(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Prod deploy", "environment": "production"})
        result = await agent.execute(ctx)
        output = DeploymentAgentOutput.model_validate(result.outputs)
        assert output.release_plan.requires_approval is True

    @pytest.mark.asyncio
    async def test_staging_no_approval_required(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Staging deploy", "environment": "staging"})
        result = await agent.execute(ctx)
        output = DeploymentAgentOutput.model_validate(result.outputs)
        assert output.release_plan.requires_approval is False

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"deployment_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
