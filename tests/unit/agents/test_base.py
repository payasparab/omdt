"""Tests for app.agents.base — BaseAgent, AgentResult, AgentContext."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult, BaseAgent


# ---------------------------------------------------------------------------
# Concrete test agent
# ---------------------------------------------------------------------------

class _StubAgent(BaseAgent):
    name = "stub_agent"
    mission = "A test stub"
    allowed_tools = ["tool_a", "tool_b"]
    required_inputs = ["message_body", "requester"]
    handoff_targets = ["data_pm"]

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(agent_name=self.name, status="success")


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------

class TestAgentResult:
    def test_defaults(self) -> None:
        r = AgentResult(agent_name="test", status="success")
        assert r.run_id  # auto-generated
        assert r.outputs == {}
        assert r.errors == []
        assert r.duration_ms == 0
        assert r.prompt_version is None

    def test_with_outputs(self) -> None:
        r = AgentResult(
            agent_name="test",
            status="failure",
            outputs={"key": "val"},
            errors=["something broke"],
            duration_ms=150,
        )
        assert r.status == "failure"
        assert r.outputs["key"] == "val"
        assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# AgentContext
# ---------------------------------------------------------------------------

class TestAgentContext:
    def test_defaults(self) -> None:
        ctx = AgentContext(correlation_id="corr-123")
        assert ctx.actor_type == "system"
        assert ctx.actor_id == "omdt"
        assert ctx.allowed_tools == []
        assert ctx.input_data == {}

    def test_with_all_fields(self) -> None:
        ctx = AgentContext(
            correlation_id="corr-1",
            work_item_id="wi-1",
            project_id="proj-1",
            actor_type="human",
            actor_id="payas",
            allowed_tools=["tool_a"],
            input_data={"foo": "bar"},
        )
        assert ctx.work_item_id == "wi-1"
        assert ctx.input_data["foo"] == "bar"


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class TestBaseAgent:
    def test_validate_inputs_all_present(self) -> None:
        agent = _StubAgent()
        missing = agent.validate_inputs({"message_body": "hi", "requester": "bob"})
        assert missing == []

    def test_validate_inputs_missing_fields(self) -> None:
        agent = _StubAgent()
        missing = agent.validate_inputs({"message_body": "hi"})
        assert missing == ["requester"]

    def test_validate_inputs_empty(self) -> None:
        agent = _StubAgent()
        missing = agent.validate_inputs({})
        assert missing == ["message_body", "requester"]

    def test_validate_outputs_valid(self) -> None:
        agent = _StubAgent()
        # Default output_schema is BaseModel, so empty dict is valid
        assert agent.validate_outputs({}) is True

    def test_validate_outputs_invalid(self) -> None:
        # With a custom schema that requires fields, validation should fail
        from pydantic import BaseModel as PB

        class StrictSchema(PB):
            required_field: str

        agent = _StubAgent()
        agent.output_schema = StrictSchema  # type: ignore[assignment]
        assert agent.validate_outputs({}) is False

    def test_get_prompt_file_not_found(self) -> None:
        agent = _StubAgent()
        with pytest.raises(FileNotFoundError, match="stub_agent"):
            agent.get_prompt()

    def test_get_prompt_loads_existing_file(self) -> None:
        # triage_agent has a real prompt file
        from app.agents.triage.service import TriageAgent

        agent = TriageAgent()
        prompt = agent.get_prompt()
        assert "# Triage Agent" in prompt
        assert "Mission" in prompt

    def test_get_prompt_version_returns_hash(self) -> None:
        from app.agents.triage.service import TriageAgent

        agent = TriageAgent()
        version = agent.get_prompt_version()
        assert len(version) == 16  # sha256[:16]

    def test_get_handoff_targets(self) -> None:
        agent = _StubAgent()
        assert agent.get_handoff_targets() == ["data_pm"]

    @pytest.mark.asyncio
    async def test_execute_returns_result(self) -> None:
        agent = _StubAgent()
        ctx = AgentContext(correlation_id="corr-test")
        result = await agent.execute(ctx)
        assert result.status == "success"
        assert result.agent_name == "stub_agent"
