"""Tests for app.core.events — EventBus, DomainEvent, event names."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.core.events import (
    DomainEvent,
    DomainEventNames,
    EventBus,
    emit_event,
)


# ---------------------------------------------------------------------------
# DomainEventNames
# ---------------------------------------------------------------------------

class TestDomainEventNames:
    def test_all_names_returns_non_empty_list(self) -> None:
        names = DomainEventNames.all_names()
        assert len(names) >= 30  # Appendix B specifies 30 events

    def test_all_names_are_dotted(self) -> None:
        for name in DomainEventNames.all_names():
            assert "." in name, f"{name} is not dotted"

    def test_known_events_present(self) -> None:
        names = DomainEventNames.all_names()
        assert "intake.received" in names
        assert "work_item.created" in names
        assert "deployment.started" in names
        assert "audit.record_written" in names
        assert "communication.sent" in names


# ---------------------------------------------------------------------------
# DomainEvent model
# ---------------------------------------------------------------------------

class TestDomainEvent:
    def test_creates_with_defaults(self) -> None:
        evt = DomainEvent(
            event_name="test.event",
            actor_type="system",
            actor_id="test",
            object_type="widget",
            object_id="w-1",
        )
        assert evt.event_id  # auto-generated
        assert evt.timestamp <= datetime.now(timezone.utc)
        assert evt.payload == {}
        assert evt.metadata == {}

    def test_payload_round_trip(self) -> None:
        evt = DomainEvent(
            event_name="test.event",
            actor_type="human",
            actor_id="u-1",
            object_type="item",
            object_id="i-1",
            payload={"key": "value"},
        )
        assert evt.payload["key"] == "value"


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestEventBus:
    def test_subscribe_and_emit_sync(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        bus.subscribe("test.ping", lambda e: received.append(e))

        evt = DomainEvent(
            event_name="test.ping",
            actor_type="system",
            actor_id="test",
            object_type="x",
            object_id="1",
        )
        bus.emit_sync(evt)
        assert len(received) == 1
        assert received[0].event_id == evt.event_id

    def test_no_cross_talk(self) -> None:
        bus = EventBus()
        received: list[str] = []
        bus.subscribe("a.event", lambda e: received.append("a"))
        bus.subscribe("b.event", lambda e: received.append("b"))

        bus.emit_sync(
            DomainEvent(
                event_name="a.event",
                actor_type="system",
                actor_id="s",
                object_type="x",
                object_id="1",
            )
        )
        assert received == ["a"]

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        calls: list[int] = []
        handler = lambda e: calls.append(1)
        bus.subscribe("x.y", handler)
        bus.unsubscribe("x.y", handler)
        bus.emit_sync(
            DomainEvent(
                event_name="x.y",
                actor_type="system",
                actor_id="s",
                object_type="x",
                object_id="1",
            )
        )
        assert calls == []

    def test_handler_count(self) -> None:
        bus = EventBus()
        assert bus.handler_count("foo") == 0
        bus.subscribe("foo", lambda e: None)
        assert bus.handler_count("foo") == 1

    @pytest.mark.asyncio
    async def test_async_emit(self) -> None:
        bus = EventBus()
        received: list[str] = []

        async def handler(e: DomainEvent) -> None:
            received.append(e.event_name)

        bus.subscribe("async.test", handler)
        await bus.emit(
            DomainEvent(
                event_name="async.test",
                actor_type="system",
                actor_id="s",
                object_type="x",
                object_id="1",
            )
        )
        assert received == ["async.test"]


# ---------------------------------------------------------------------------
# emit_event convenience
# ---------------------------------------------------------------------------

class TestEmitEvent:
    def test_returns_event_and_triggers_handler(self) -> None:
        bus = EventBus()
        seen: list[DomainEvent] = []
        bus.subscribe("artifact.created", lambda e: seen.append(e))

        evt = emit_event(
            bus,
            "artifact.created",
            object_type="artifact",
            object_id="a-1",
            payload={"name": "report.pdf"},
        )
        assert evt.event_name == "artifact.created"
        assert len(seen) == 1
