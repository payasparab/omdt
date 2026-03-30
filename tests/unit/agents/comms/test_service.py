"""Tests for app.agents.comms.service — CommsPublishingAgent."""
from __future__ import annotations

import pytest

from app.agents.comms.service import CommsPublishingAgent, CommsPublishingOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> CommsPublishingAgent:
    return CommsPublishingAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestCommsPublishingAgent:
    def test_name(self) -> None:
        assert CommsPublishingAgent().name == "comms_publishing_agent"

    def test_required_inputs(self) -> None:
        assert "comms_request" in CommsPublishingAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = CommsPublishingAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_email_package(self, agent, context_factory) -> None:
        ctx = context_factory({
            "comms_request": "Announce dashboard launch",
            "milestone": "Dashboard v1.0",
            "recipients": ["team@example.com"],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = CommsPublishingOutput.model_validate(result.outputs)
        assert output.email_package is not None
        assert "Dashboard v1.0" in output.email_package.subject
        assert "team@example.com" in output.email_package.recipients

    @pytest.mark.asyncio
    async def test_produces_publish_request(self, agent, context_factory) -> None:
        ctx = context_factory({"comms_request": "Publish update", "channel": "notion"})
        result = await agent.execute(ctx)
        output = CommsPublishingOutput.model_validate(result.outputs)
        assert output.publish_request is not None
        assert output.publish_request.channel == "notion"

    @pytest.mark.asyncio
    async def test_produces_update_note(self, agent, context_factory) -> None:
        ctx = context_factory({"comms_request": "Milestone reached", "milestone": "Phase 2 complete"})
        result = await agent.execute(ctx)
        output = CommsPublishingOutput.model_validate(result.outputs)
        assert output.update_note is not None
        assert output.update_note.milestone == "Phase 2 complete"
        assert len(output.update_note.key_changes) > 0

    @pytest.mark.asyncio
    async def test_default_channel_is_email(self, agent, context_factory) -> None:
        ctx = context_factory({"comms_request": "Default channel test"})
        result = await agent.execute(ctx)
        output = CommsPublishingOutput.model_validate(result.outputs)
        assert output.publish_request.channel == "email"

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"comms_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
