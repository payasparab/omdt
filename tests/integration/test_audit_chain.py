"""Integration test: verify audit hash chain integrity and tamper detection."""
from __future__ import annotations

import pytest

from app.core.audit import AuditEvent, AuditReader, AuditWriter


class TestAuditChainIntegrity:
    """Perform multiple operations -> verify hash chain -> detect tampering."""

    def test_chain_integrity_with_multiple_events(self) -> None:
        """Write multiple audit events and verify chain is intact."""
        writer = AuditWriter()
        reader = AuditReader(writer)

        for i in range(10):
            event = AuditEvent(
                sequence_number=0,
                event_name=f"test.event_{i}",
                actor_type="system",
                actor_id="test",
                object_type="test_object",
                object_id=f"obj-{i}",
                change_summary=f"Test event {i}",
            )
            writer.append(event)

        assert len(writer.records) == 10
        assert reader.verify_chain() is True

    def test_chain_detects_tampered_hash(self) -> None:
        """Tampering with an event_hash breaks chain verification."""
        writer = AuditWriter()
        reader = AuditReader(writer)

        for i in range(5):
            event = AuditEvent(
                sequence_number=0,
                event_name=f"test.event_{i}",
                actor_type="system",
                actor_id="test",
                object_type="work_item",
                object_id=f"wi-{i}",
                change_summary=f"Event {i}",
            )
            writer.append(event)

        assert reader.verify_chain() is True

        # Tamper with the middle event's hash
        writer._records[2].event_hash = "tampered_hash_value"
        assert reader.verify_chain() is False

    def test_chain_detects_tampered_prev_hash(self) -> None:
        """Tampering with prev_event_hash breaks chain verification."""
        writer = AuditWriter()
        reader = AuditReader(writer)

        for i in range(5):
            event = AuditEvent(
                sequence_number=0,
                event_name=f"test.event_{i}",
                actor_type="system",
                actor_id="test",
                object_type="deployment",
                object_id=f"dep-{i}",
            )
            writer.append(event)

        assert reader.verify_chain() is True

        # Tamper with prev_event_hash
        writer._records[3].prev_event_hash = "wrong_prev_hash"
        assert reader.verify_chain() is False

    def test_chain_sequence_numbers_monotonic(self) -> None:
        """Sequence numbers increase monotonically."""
        writer = AuditWriter()

        for i in range(5):
            event = AuditEvent(
                sequence_number=0,
                event_name="test.event",
                actor_type="system",
                actor_id="test",
                object_type="audit",
                object_id=f"id-{i}",
            )
            writer.append(event)

        for i, rec in enumerate(writer.records):
            assert rec.sequence_number == i + 1

    def test_first_event_has_no_prev_hash(self) -> None:
        """The first event in the chain has prev_event_hash = None."""
        writer = AuditWriter()

        event = AuditEvent(
            sequence_number=0,
            event_name="test.first",
            actor_type="system",
            actor_id="test",
            object_type="test",
            object_id="first",
        )
        writer.append(event)

        assert writer.records[0].prev_event_hash is None
        assert writer.records[0].event_hash != ""

    def test_chain_links_correctly(self) -> None:
        """Each event's prev_event_hash matches the previous event's event_hash."""
        writer = AuditWriter()

        for i in range(5):
            event = AuditEvent(
                sequence_number=0,
                event_name="test.event",
                actor_type="system",
                actor_id="test",
                object_type="test",
                object_id=f"id-{i}",
            )
            writer.append(event)

        records = writer.records
        for i in range(1, len(records)):
            assert records[i].prev_event_hash == records[i - 1].event_hash

    def test_empty_chain_verifies(self) -> None:
        """An empty chain is considered valid."""
        writer = AuditWriter()
        reader = AuditReader(writer)
        assert reader.verify_chain() is True

    def test_reader_query_filters(self) -> None:
        """AuditReader query filtering works correctly."""
        writer = AuditWriter()
        reader = AuditReader(writer)

        for i in range(3):
            event = AuditEvent(
                sequence_number=0,
                event_name="work_item.created",
                actor_type="system",
                actor_id="test",
                object_type="work_item",
                object_id=f"wi-{i}",
            )
            writer.append(event)

        event = AuditEvent(
            sequence_number=0,
            event_name="deployment.created",
            actor_type="human",
            actor_id="admin",
            object_type="deployment",
            object_id="dep-1",
        )
        writer.append(event)

        work_item_events = reader.query(event_name="work_item.created")
        assert len(work_item_events) == 3

        deployment_events = reader.query(object_type="deployment")
        assert len(deployment_events) == 1

        admin_events = reader.query(actor_id="admin")
        assert len(admin_events) == 1
