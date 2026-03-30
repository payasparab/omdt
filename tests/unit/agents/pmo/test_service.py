"""Tests for app.agents.pmo.service — DataPMOAgent."""
from __future__ import annotations

import pytest

from app.agents.pmo.service import DataPMOAgent, DataPMOOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DataPMOAgent:
    return DataPMOAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDataPMOAgent:
    def test_name(self) -> None:
        assert DataPMOAgent().name == "data_pmo"

    def test_required_inputs(self) -> None:
        assert "report_request" in DataPMOAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataPMOAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_produces_raid_log(self, agent, context_factory) -> None:
        ctx = context_factory({"report_request": "Weekly status", "project_id": "proj-1"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DataPMOOutput.model_validate(result.outputs)
        assert output.raid_log is not None
        assert len(output.raid_log.items) >= 4
        categories = {item.category for item in output.raid_log.items}
        assert "risk" in categories
        assert "issue" in categories
        assert "dependency" in categories

    @pytest.mark.asyncio
    async def test_produces_status_digest(self, agent, context_factory) -> None:
        ctx = context_factory({"report_request": "Standup summary"})
        result = await agent.execute(ctx)
        output = DataPMOOutput.model_validate(result.outputs)
        assert output.status_digest is not None
        assert len(output.status_digest.completed) > 0
        assert len(output.status_digest.in_progress) > 0

    @pytest.mark.asyncio
    async def test_produces_follow_up_queue(self, agent, context_factory) -> None:
        ctx = context_factory({"report_request": "Follow ups"})
        result = await agent.execute(ctx)
        output = DataPMOOutput.model_validate(result.outputs)
        assert len(output.follow_up_queue) > 0

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"report_request": "Test"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
