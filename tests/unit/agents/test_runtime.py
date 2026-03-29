"""Tests for app.agents.runtime — AgentRuntime execution, events, audit."""
from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.runtime import (
    AGENT_RUN_COMPLETED,
    AGENT_RUN_FAILED,
    AGENT_RUN_STARTED,
    AgentRuntime,
)
from app.core.audit import AuditWriter
from app.core.events import DomainEvent, EventBus


# ---------------------------------------------------------------------------
# Test agents
# ---------------------------------------------------------------------------

class _SuccessAgent(BaseAgent):
    name = "success_agent"
    mission = "Always succeeds"

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs={"answer": 42},
        )


class _FailAgent(BaseAgent):
    name = "fail_agent"
    mission = "Always fails"

    async def execute(self, context: AgentContext) -> AgentResult:
        raise ValueError("Something went wrong")


class _SlowAgent(BaseAgent):
    name = "slow_agent"
    mission = "Takes too long"

    async def execute(self, context: AgentContext) -> AgentResult:
        await asyncio.sleep(10)
        return AgentResult(agent_name=self.name, status="success")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register("success_agent", _SuccessAgent)
    reg.register("fail_agent", _FailAgent)
    reg.register("slow_agent", _SlowAgent)
    return reg


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def audit_writer() -> AuditWriter:
    return AuditWriter()


@pytest.fixture
def runtime(registry: AgentRegistry, event_bus: EventBus, audit_writer: AuditWriter) -> AgentRuntime:
    return AgentRuntime(registry, event_bus, audit_writer)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentRuntime:
    @pytest.mark.asyncio
    async def test_successful_execution(self, runtime: AgentRuntime) -> None:
        result = await runtime.execute("success_agent", {"key": "val"})
        assert result.status == "success"
        assert result.agent_name == "success_agent"
        assert result.outputs["answer"] == 42
        assert result.duration_ms >= 0
        assert result.run_id

    @pytest.mark.asyncio
    async def test_creates_agent_run_record(self, runtime: AgentRuntime) -> None:
        await runtime.execute("success_agent", {})
        assert len(runtime.runs) == 1
        run = runtime.runs[0]
        assert run.agent_name == "success_agent"
        assert run.status == "success"
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_emits_started_and_completed_events(
        self, runtime: AgentRuntime, event_bus: EventBus
    ) -> None:
        events: list[DomainEvent] = []
        event_bus.subscribe(AGENT_RUN_STARTED, lambda e: events.append(e))
        event_bus.subscribe(AGENT_RUN_COMPLETED, lambda e: events.append(e))

        await runtime.execute("success_agent", {})
        event_names = [e.event_name for e in events]
        assert AGENT_RUN_STARTED in event_names
        assert AGENT_RUN_COMPLETED in event_names

    @pytest.mark.asyncio
    async def test_failure_emits_failed_event(
        self, runtime: AgentRuntime, event_bus: EventBus
    ) -> None:
        events: list[DomainEvent] = []
        event_bus.subscribe(AGENT_RUN_FAILED, lambda e: events.append(e))

        result = await runtime.execute("fail_agent", {})
        assert result.status == "failure"
        assert "Something went wrong" in result.errors[0]
        assert len(events) == 1
        assert events[0].payload["status"] == "failure"

    @pytest.mark.asyncio
    async def test_failure_creates_run_record(self, runtime: AgentRuntime) -> None:
        await runtime.execute("fail_agent", {})
        assert len(runtime.runs) == 1
        assert runtime.runs[0].status == "failure"

    @pytest.mark.asyncio
    async def test_timeout_handling(
        self, registry: AgentRegistry, event_bus: EventBus, audit_writer: AuditWriter
    ) -> None:
        rt = AgentRuntime(registry, event_bus, audit_writer, default_timeout_seconds=0.1)
        events: list[DomainEvent] = []
        event_bus.subscribe(AGENT_RUN_FAILED, lambda e: events.append(e))

        result = await rt.execute("slow_agent", {})
        assert result.status == "timeout"
        assert "timed out" in result.errors[0]
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_audit_record_written(
        self, runtime: AgentRuntime, audit_writer: AuditWriter
    ) -> None:
        await runtime.execute("success_agent", {})
        assert len(audit_writer.records) == 1
        record = audit_writer.records[0]
        assert "success_agent" in record.change_summary
        assert record.object_type == "agent_run"

    @pytest.mark.asyncio
    async def test_correlation_id_passed_through(self, runtime: AgentRuntime) -> None:
        result = await runtime.execute(
            "success_agent", {}, correlation_id="corr-custom-123"
        )
        run = runtime.runs[0]
        assert run.correlation_id == "corr-custom-123"

    @pytest.mark.asyncio
    async def test_multiple_runs_tracked(self, runtime: AgentRuntime) -> None:
        await runtime.execute("success_agent", {})
        await runtime.execute("success_agent", {})
        await runtime.execute("fail_agent", {})
        assert len(runtime.runs) == 3

    @pytest.mark.asyncio
    async def test_unknown_agent_raises(self, runtime: AgentRuntime) -> None:
        with pytest.raises(KeyError, match="nonexistent"):
            await runtime.execute("nonexistent", {})
