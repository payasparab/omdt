"""Agent runtime — executes agents with full observability."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.registry import AgentRegistry
from app.core.audit import AuditEvent, AuditWriter
from app.core.events import DomainEvent, EventBus
from app.core.ids import generate_id, set_correlation_id
from app.domain.models.agent_run import AgentRun


# ---------------------------------------------------------------------------
# Agent event names
# ---------------------------------------------------------------------------

AGENT_RUN_STARTED = "agent.run_started"
AGENT_RUN_COMPLETED = "agent.run_completed"
AGENT_RUN_FAILED = "agent.run_failed"


# ---------------------------------------------------------------------------
# AgentRuntime
# ---------------------------------------------------------------------------

class AgentRuntime:
    """Executes registered agents with event emission, audit recording,
    timeout enforcement, and AgentRun tracking.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: EventBus,
        audit_writer: AuditWriter,
        default_timeout_seconds: float = 300.0,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._audit_writer = audit_writer
        self._default_timeout = default_timeout_seconds
        self._runs: list[AgentRun] = []

    @property
    def runs(self) -> list[AgentRun]:
        """Return a copy of all recorded agent runs."""
        return list(self._runs)

    async def execute(
        self,
        agent_name: str,
        inputs: dict,
        correlation_id: str | None = None,
        actor: str = "system",
        timeout_seconds: float | None = None,
    ) -> AgentResult:
        """Execute *agent_name* with full observability.

        Creates an AgentRun record, emits domain events, records an
        audit entry, and enforces a timeout.
        """
        run_id = generate_id()
        corr_id = correlation_id or generate_id()
        set_correlation_id(corr_id)
        timeout = timeout_seconds or self._default_timeout

        # Resolve agent class and definition
        defn = self._registry.get(agent_name)
        agent_class = self._registry.get_class(agent_name)
        agent: BaseAgent = agent_class()

        # Build prompt version
        prompt_version = defn.prompt_version or ""

        # Create AgentRun record
        started_at = datetime.now(timezone.utc)
        agent_run = AgentRun(
            id=run_id,  # type: ignore[arg-type]
            work_item_id=None,
            agent_name=agent_name,
            prompt_version=prompt_version,
            status="running",
            correlation_id=corr_id,
            started_at=started_at,
        )

        # Build context
        context = AgentContext(
            correlation_id=corr_id,
            work_item_id=inputs.get("work_item_id"),
            project_id=inputs.get("project_id"),
            actor_type="agent" if actor != "human" else "human",
            actor_id=actor,
            allowed_tools=list(defn.allowed_tools),
            input_data=inputs,
        )

        # Emit started event
        await self._event_bus.emit(DomainEvent(
            event_name=AGENT_RUN_STARTED,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            object_type="agent_run",
            object_id=run_id,
            payload={"agent_name": agent_name, "inputs": inputs},
        ))

        # Execute with timeout
        start_ms = time.monotonic_ns() // 1_000_000
        try:
            result = await asyncio.wait_for(
                agent.execute(context),
                timeout=timeout,
            )
            result.run_id = run_id
            result.prompt_version = prompt_version
            elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms
            result.duration_ms = elapsed_ms

            # Update AgentRun
            agent_run.status = result.status
            agent_run.completed_at = datetime.now(timezone.utc)

            # Emit completed event
            await self._event_bus.emit(DomainEvent(
                event_name=AGENT_RUN_COMPLETED,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                object_type="agent_run",
                object_id=run_id,
                payload={
                    "agent_name": agent_name,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                },
            ))

        except asyncio.TimeoutError:
            elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms
            result = AgentResult(
                agent_name=agent_name,
                run_id=run_id,
                status="timeout",
                errors=[f"Agent timed out after {timeout}s"],
                duration_ms=elapsed_ms,
                prompt_version=prompt_version,
            )
            agent_run.status = "timeout"
            agent_run.completed_at = datetime.now(timezone.utc)

            await self._event_bus.emit(DomainEvent(
                event_name=AGENT_RUN_FAILED,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                object_type="agent_run",
                object_id=run_id,
                payload={
                    "agent_name": agent_name,
                    "status": "timeout",
                    "error": result.errors[0],
                },
            ))

        except Exception as exc:
            elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms
            result = AgentResult(
                agent_name=agent_name,
                run_id=run_id,
                status="failure",
                errors=[str(exc)],
                duration_ms=elapsed_ms,
                prompt_version=prompt_version,
            )
            agent_run.status = "failure"
            agent_run.completed_at = datetime.now(timezone.utc)

            await self._event_bus.emit(DomainEvent(
                event_name=AGENT_RUN_FAILED,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                object_type="agent_run",
                object_id=run_id,
                payload={
                    "agent_name": agent_name,
                    "status": "failure",
                    "error": str(exc),
                },
            ))

        # Record AgentRun
        self._runs.append(agent_run)

        # Write audit record
        self._audit_writer.append(AuditEvent(
            sequence_number=0,  # assigned by writer
            event_name=f"agent.run.{result.status}",
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            correlation_id=corr_id,
            object_type="agent_run",
            object_id=run_id,
            change_summary=(
                f"Agent '{agent_name}' completed with status "
                f"'{result.status}' in {result.duration_ms}ms "
                f"(prompt_version={prompt_version})"
            ),
        ))

        return result
