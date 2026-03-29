"""Tests for AuditEvent domain model."""
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.enums import ActorType
from app.domain.models.audit import AuditEvent, DomainEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestAuditEventCreation:
    def test_minimal_valid(self) -> None:
        ae = AuditEvent(
            audit_event_id=uuid4(),
            sequence_number=1,
            event_time=_now(),
            event_name="work_item.created",
            actor_type=ActorType.SYSTEM,
            actor_id="intake-router",
            correlation_id="corr-001",
            object_type="work_item",
            object_id=str(uuid4()),
            change_summary="Created work item from Outlook intake",
            event_hash="b" * 64,
        )
        assert ae.prev_event_hash is None
        assert ae.tool_name is None

    def test_hash_chain_fields(self) -> None:
        ae = AuditEvent(
            audit_event_id=uuid4(),
            sequence_number=2,
            event_time=_now(),
            event_name="work_item.updated",
            actor_type=ActorType.AGENT,
            actor_id="triage-agent",
            correlation_id="corr-002",
            object_type="work_item",
            object_id=str(uuid4()),
            change_summary="State changed to TRIAGE",
            prev_event_hash="b" * 64,
            event_hash="c" * 64,
        )
        assert ae.prev_event_hash == "b" * 64


class TestDomainEventCreation:
    def test_minimal_valid(self) -> None:
        de = DomainEvent(
            id=uuid4(),
            event_name="work_item.state_changed",
            aggregate_type="work_item",
            aggregate_id=str(uuid4()),
            correlation_id="corr-003",
            created_at=_now(),
        )
        assert de.payload == {}
        assert de.actor_type is None
