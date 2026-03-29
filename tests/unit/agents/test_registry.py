"""Tests for app.agents.registry — AgentRegistry, AgentDefinition."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.registry import AgentDefinition, AgentRegistry


# ---------------------------------------------------------------------------
# Stub agent for testing
# ---------------------------------------------------------------------------

class _MockAgent(BaseAgent):
    name = "mock_agent"
    mission = "Testing agent"
    allowed_tools = ["tool_x"]
    required_inputs = ["data"]
    handoff_targets = ["other_agent"]

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(agent_name=self.name, status="success")


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------

class TestAgentDefinition:
    def test_create_minimal(self) -> None:
        d = AgentDefinition(name="test")
        assert d.name == "test"
        assert d.allowed_tools == []
        assert d.handoff_targets == []

    def test_create_full(self) -> None:
        d = AgentDefinition(
            name="full",
            description="Full agent",
            prompt_path="prompts/system/test.md",
            prompt_version="abc123",
            allowed_tools=["t1", "t2"],
            required_inputs=["in1"],
            output_schema="TestOutput",
            escalation_rules=["rule1"],
            approval_boundaries=["boundary1"],
            handoff_targets=["agent_x"],
        )
        assert d.allowed_tools == ["t1", "t2"]
        assert d.output_schema == "TestOutput"


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_register_and_get(self) -> None:
        reg = AgentRegistry()
        reg.register("mock_agent", _MockAgent, prompt_path="prompts/system/mock.md")
        defn = reg.get("mock_agent")
        assert defn.name == "mock_agent"
        assert defn.allowed_tools == ["tool_x"]
        assert defn.handoff_targets == ["other_agent"]

    def test_get_nonexistent_raises(self) -> None:
        reg = AgentRegistry()
        with pytest.raises(KeyError, match="not_registered"):
            reg.get("not_registered")

    def test_get_class(self) -> None:
        reg = AgentRegistry()
        reg.register("mock_agent", _MockAgent)
        cls = reg.get_class("mock_agent")
        assert cls is _MockAgent

    def test_get_class_nonexistent_raises(self) -> None:
        reg = AgentRegistry()
        with pytest.raises(KeyError):
            reg.get_class("missing")

    def test_list_agents(self) -> None:
        reg = AgentRegistry()
        reg.register("a", _MockAgent)
        reg.register("b", _MockAgent)
        agents = reg.list_agents()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert names == {"a", "b"}

    def test_list_agents_empty(self) -> None:
        reg = AgentRegistry()
        assert reg.list_agents() == []

    def test_validate_all_no_errors_when_prompt_exists(self) -> None:
        reg = AgentRegistry()
        # Register triage agent which has a real prompt file
        from app.agents.triage.service import TriageAgent

        reg.register(
            "triage_agent",
            TriageAgent,
            prompt_path="prompts/system/triage_agent.md",
        )
        errors = reg.validate_all()
        assert errors == []

    def test_validate_all_reports_missing_prompt(self) -> None:
        reg = AgentRegistry()
        reg.register(
            "mock_agent",
            _MockAgent,
            prompt_path="prompts/system/nonexistent.md",
        )
        errors = reg.validate_all()
        assert any("nonexistent.md" in e for e in errors)

    def test_load_from_config(self) -> None:
        reg = AgentRegistry()
        names = reg.load_from_config()
        assert "triage_agent" in names
        assert "data_pm" in names
        assert len(names) == 20
