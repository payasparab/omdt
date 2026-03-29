"""Tests for app.services.triage — TriageService workflow."""
from __future__ import annotations

import pytest

from app.core.audit import AuditWriter
from app.core.events import DomainEvent, DomainEventNames, EventBus
from app.services.triage import TriageService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def audit_writer() -> AuditWriter:
    return AuditWriter()


@pytest.fixture
def svc(event_bus: EventBus, audit_writer: AuditWriter) -> TriageService:
    return TriageService(event_bus, audit_writer)


class TestProcessTriage:
    @pytest.mark.asyncio
    async def test_returns_triage_output(self, svc: TriageService) -> None:
        output = await svc.process_triage(
            "wi-1", {"message_body": "Build an analysis report on sales metrics"}
        )
        assert output.route_key == "analysis_request"
        assert output.normalized_title

    @pytest.mark.asyncio
    async def test_emits_route_proposed_event(
        self, svc: TriageService, event_bus: EventBus
    ) -> None:
        events: list[DomainEvent] = []
        event_bus.subscribe(
            DomainEventNames.TRIAGE_ROUTE_PROPOSED,
            lambda e: events.append(e),
        )
        await svc.process_triage("wi-2", {"message_body": "Need a new pipeline"})
        assert len(events) == 1
        assert events[0].payload["route_key"] == "pipeline_request"

    @pytest.mark.asyncio
    async def test_creates_audit_record(
        self, svc: TriageService, audit_writer: AuditWriter
    ) -> None:
        await svc.process_triage("wi-3", {"message_body": "Access request"})
        assert len(audit_writer.records) >= 1
        assert any("triage" in r.event_name for r in audit_writer.records)

    @pytest.mark.asyncio
    async def test_stores_result(self, svc: TriageService) -> None:
        await svc.process_triage("wi-4", {"message_body": "Something"})
        result = svc.get_triage_result("wi-4")
        assert result is not None

    @pytest.mark.asyncio
    async def test_opens_clarification_thread_when_needed(
        self, svc: TriageService, event_bus: EventBus
    ) -> None:
        events: list[DomainEvent] = []
        event_bus.subscribe(
            DomainEventNames.TRIAGE_CLARIFICATION_REQUESTED,
            lambda e: events.append(e),
        )
        # Minimal input triggers clarification
        await svc.process_triage("wi-5", {"message_body": "Do something"})
        assert len(events) >= 1


class TestClarificationLoop:
    @pytest.mark.asyncio
    async def test_request_clarification_creates_thread(self, svc: TriageService) -> None:
        thread_id = await svc.request_clarification(
            "wi-10",
            [{"field_name": "business_goal", "question": "What is the goal?"}],
        )
        thread = svc.get_thread(thread_id)
        assert thread is not None
        assert thread.work_item_id == "wi-10"
        assert thread.status == "open"

    @pytest.mark.asyncio
    async def test_receive_response_updates_thread(self, svc: TriageService) -> None:
        # First triage to populate result
        await svc.process_triage("wi-11", {"message_body": "Build something"})

        # Find thread
        threads = [t for t in svc._threads.values() if t.work_item_id == "wi-11"]
        assert len(threads) >= 1
        thread = threads[0]

        # Send response
        new_output = await svc.receive_clarification_response(
            thread.thread_id,
            {
                "responder": "payas",
                "message_body": "The goal is to track revenue from analysis data",
                "business_goal": "Track revenue",
            },
        )
        assert thread.status == "resolved"
        assert new_output is not None

    @pytest.mark.asyncio
    async def test_receive_response_unknown_thread(self, svc: TriageService) -> None:
        result = await svc.receive_clarification_response(
            "nonexistent", {"responder": "someone"}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_clarification_emits_events(
        self, svc: TriageService, event_bus: EventBus
    ) -> None:
        request_events: list[DomainEvent] = []
        receive_events: list[DomainEvent] = []
        event_bus.subscribe(
            DomainEventNames.TRIAGE_CLARIFICATION_REQUESTED,
            lambda e: request_events.append(e),
        )
        event_bus.subscribe(
            DomainEventNames.TRIAGE_CLARIFICATION_RECEIVED,
            lambda e: receive_events.append(e),
        )

        # Process triage (will open clarification)
        await svc.process_triage("wi-12", {"message_body": "Hello"})
        assert len(request_events) >= 1

        # Find thread and respond
        threads = [t for t in svc._threads.values() if t.work_item_id == "wi-12"]
        if threads:
            await svc.receive_clarification_response(
                threads[0].thread_id,
                {"responder": "user", "message_body": "Here is more info"},
            )
            assert len(receive_events) >= 1

    @pytest.mark.asyncio
    async def test_audit_records_for_clarification(
        self, svc: TriageService, audit_writer: AuditWriter
    ) -> None:
        await svc.process_triage("wi-13", {"message_body": "Unclear request"})
        audit_events = [r for r in audit_writer.records if "clarification" in r.event_name]
        assert len(audit_events) >= 1
