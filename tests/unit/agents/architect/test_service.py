"""Tests for app.agents.architect.service — DataArchitectAgent."""
from __future__ import annotations

import pytest

from app.agents.architect.service import DataArchitectAgent, DataArchitectOutput
from app.agents.base import AgentContext


@pytest.fixture
def agent() -> DataArchitectAgent:
    return DataArchitectAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(correlation_id="corr-test", work_item_id="wi-test", input_data=input_data)
    return _make


class TestDataArchitectAgent:
    def test_name(self) -> None:
        assert DataArchitectAgent().name == "data_architect"

    def test_required_inputs(self) -> None:
        assert "model_request" in DataArchitectAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = DataArchitectAgent()
        assert "data_engineer" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_input_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_dbml_output(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "User schema", "output_format": "dbml", "tables": ["users", "orders"]})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = DataArchitectOutput.model_validate(result.outputs)
        assert output.dbml is not None
        assert len(output.dbml.tables) == 2
        assert "Table users" in output.dbml.dbml_content

    @pytest.mark.asyncio
    async def test_diagram_output(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "Data flow", "output_format": "diagram"})
        result = await agent.execute(ctx)
        output = DataArchitectOutput.model_validate(result.outputs)
        assert output.architecture_diagram is not None
        assert output.architecture_diagram.mermaid_content != ""

    @pytest.mark.asyncio
    async def test_contract_output(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "Data contract", "output_format": "contract"})
        result = await agent.execute(ctx)
        output = DataArchitectOutput.model_validate(result.outputs)
        assert len(output.data_contracts) > 0

    @pytest.mark.asyncio
    async def test_full_output(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "Full architecture", "output_format": "full"})
        result = await agent.execute(ctx)
        output = DataArchitectOutput.model_validate(result.outputs)
        assert output.dbml is not None
        assert output.architecture_diagram is not None
        assert len(output.data_contracts) > 0

    @pytest.mark.asyncio
    async def test_invalid_format_fails(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "Test", "output_format": "bad"})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_output_conforms_to_schema(self, agent, context_factory) -> None:
        ctx = context_factory({"model_request": "Test", "output_format": "full"})
        result = await agent.execute(ctx)
        assert agent.validate_outputs(result.outputs)
