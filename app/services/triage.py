"""Triage service — orchestrates the triage workflow from section 11.3.

Coordinates the TriageAgent, manages clarification loops, and updates
work items with routing decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentContext, AgentResult
from app.agents.routing import route_to_agent
from app.agents.triage.schemas import TriageOutput
from app.agents.triage.service import TriageAgent
from app.core.audit import AuditEvent, AuditWriter
from app.core.events import DomainEvent, DomainEventNames, EventBus
from app.core.ids import generate_correlation_id, generate_id


# ---------------------------------------------------------------------------
# Triage workflow states (§11.3)
# ---------------------------------------------------------------------------
# NEW INTAKE -> NORMALIZED -> ROUTE_PROPOSED -> NEEDS_CLARIFICATION?
#   -> CLARIFICATION_OPEN -> CLARIFICATION_RESPONSE_RECEIVED -> RE-EVALUATE
# -> READY_FOR_PRD -> PRD_DRAFTING -> ...


class ClarificationThread:
    """Tracks a clarification conversation for a work item."""

    def __init__(
        self,
        thread_id: str,
        work_item_id: str,
        questions: list[dict[str, str]],
    ) -> None:
        self.thread_id = thread_id
        self.work_item_id = work_item_id
        self.questions = questions
        self.responses: list[dict[str, Any]] = []
        self.status: str = "open"  # open, responded, resolved
        self.created_at: datetime = datetime.now(timezone.utc)


class TriageService:
    """Orchestrates the triage workflow.

    Runs the TriageAgent, manages clarification threads,
    and coordinates re-evaluation after clarification responses.
    """

    def __init__(
        self,
        event_bus: EventBus,
        audit_writer: AuditWriter,
    ) -> None:
        self._event_bus = event_bus
        self._audit_writer = audit_writer
        self._agent = TriageAgent()
        self._threads: dict[str, ClarificationThread] = {}
        self._triage_results: dict[str, TriageOutput] = {}

    async def process_triage(
        self,
        work_item_id: str,
        inputs: dict[str, Any],
        correlation_id: str | None = None,
    ) -> TriageOutput:
        """Run the triage agent on a work item and return the result.

        Updates the work item with route and priority, emits events,
        and opens a clarification thread if needed.
        """
        corr_id = correlation_id or generate_correlation_id()

        context = AgentContext(
            correlation_id=corr_id,
            work_item_id=work_item_id,
            actor_type="system",
            actor_id="triage_service",
            input_data=inputs,
        )

        result: AgentResult = await self._agent.execute(context)

        if result.status != "success":
            # Emit failure event
            await self._event_bus.emit(DomainEvent(
                event_name="triage.failed",
                actor_type="system",
                actor_id="triage_service",
                object_type="work_item",
                object_id=work_item_id,
                payload={"errors": result.errors},
            ))
            raise RuntimeError(
                f"Triage failed for work_item {work_item_id}: {result.errors}"
            )

        triage_output = TriageOutput.model_validate(result.outputs)
        self._triage_results[work_item_id] = triage_output

        # Emit route proposed event
        await self._event_bus.emit(DomainEvent(
            event_name=DomainEventNames.TRIAGE_ROUTE_PROPOSED,
            actor_type="agent",
            actor_id="triage_agent",
            object_type="work_item",
            object_id=work_item_id,
            payload={
                "route_key": triage_output.route_key,
                "confidence": triage_output.confidence,
                "priority": triage_output.priority.value,
                "work_item_type": triage_output.work_item_type.value,
                "recommended_next_state": triage_output.recommended_next_state.value,
            },
        ))

        # Audit
        self._audit_writer.append(AuditEvent(
            sequence_number=0,
            event_name="triage.route_proposed",
            actor_type="agent",
            actor_id="triage_agent",
            correlation_id=corr_id,
            object_type="work_item",
            object_id=work_item_id,
            change_summary=(
                f"Triage proposed route '{triage_output.route_key}' "
                f"with confidence {triage_output.confidence}"
            ),
        ))

        # If clarification needed, open a thread
        if triage_output.clarification_questions:
            await self.request_clarification(
                work_item_id,
                [q.model_dump() for q in triage_output.clarification_questions],
                correlation_id=corr_id,
            )

        return triage_output

    async def request_clarification(
        self,
        work_item_id: str,
        questions: list[dict[str, str]],
        correlation_id: str | None = None,
    ) -> str:
        """Create a clarification thread for a work item.

        Returns the thread_id.
        """
        corr_id = correlation_id or generate_correlation_id()
        thread_id = generate_id()
        thread = ClarificationThread(
            thread_id=thread_id,
            work_item_id=work_item_id,
            questions=questions,
        )
        self._threads[thread_id] = thread

        await self._event_bus.emit(DomainEvent(
            event_name=DomainEventNames.TRIAGE_CLARIFICATION_REQUESTED,
            actor_type="agent",
            actor_id="triage_agent",
            object_type="clarification_thread",
            object_id=thread_id,
            payload={
                "work_item_id": work_item_id,
                "questions": questions,
            },
        ))

        self._audit_writer.append(AuditEvent(
            sequence_number=0,
            event_name="triage.clarification_requested",
            actor_type="agent",
            actor_id="triage_agent",
            correlation_id=corr_id,
            object_type="clarification_thread",
            object_id=thread_id,
            change_summary=(
                f"Clarification requested for work_item {work_item_id}: "
                f"{len(questions)} question(s)"
            ),
        ))

        return thread_id

    async def receive_clarification_response(
        self,
        thread_id: str,
        response: dict[str, Any],
        correlation_id: str | None = None,
    ) -> TriageOutput | None:
        """Process a clarification response and re-evaluate if appropriate.

        Returns a new TriageOutput if re-evaluation was triggered, or
        None if the thread was not found.
        """
        corr_id = correlation_id or generate_correlation_id()

        thread = self._threads.get(thread_id)
        if thread is None:
            return None

        thread.responses.append(response)
        thread.status = "responded"

        await self._event_bus.emit(DomainEvent(
            event_name=DomainEventNames.TRIAGE_CLARIFICATION_RECEIVED,
            actor_type="human",
            actor_id=response.get("responder", "unknown"),
            object_type="clarification_thread",
            object_id=thread_id,
            payload={"response": response},
        ))

        self._audit_writer.append(AuditEvent(
            sequence_number=0,
            event_name="triage.clarification_received",
            actor_type="human",
            actor_id=response.get("responder", "unknown"),
            correlation_id=corr_id,
            object_type="clarification_thread",
            object_id=thread_id,
            change_summary=f"Clarification response received for thread {thread_id}",
        ))

        # Re-evaluate: merge original inputs with clarification data
        original_result = self._triage_results.get(thread.work_item_id)
        if original_result is None:
            return None

        # Build merged inputs for re-evaluation
        merged_inputs = dict(response)
        merged_inputs.setdefault("message_body", "Re-evaluation after clarification")
        thread.status = "resolved"

        return await self.process_triage(
            work_item_id=thread.work_item_id,
            inputs=merged_inputs,
            correlation_id=corr_id,
        )

    def get_thread(self, thread_id: str) -> ClarificationThread | None:
        """Return a clarification thread by ID."""
        return self._threads.get(thread_id)

    def get_triage_result(self, work_item_id: str) -> TriageOutput | None:
        """Return the most recent triage output for a work item."""
        return self._triage_results.get(work_item_id)
