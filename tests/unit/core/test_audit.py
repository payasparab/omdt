"""Tests for app.core.audit — hash chain, append-only, query, verification."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta

from app.core.audit import (
    AuditEvent,
    AuditReader,
    AuditWriter,
    compute_snapshot_hash,
    _compute_event_hash,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(**overrides: object) -> AuditEvent:
    defaults: dict = dict(
        sequence_number=0,  # writer overrides
        event_name="test.action",
        actor_type="system",
        actor_id="test-actor",
        object_type="widget",
        object_id="w-1",
        change_summary="created widget",
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)


# ---------------------------------------------------------------------------
# compute_snapshot_hash
# ---------------------------------------------------------------------------

class TestSnapshotHash:
    def test_deterministic(self) -> None:
        data = {"b": 2, "a": 1}
        h1 = compute_snapshot_hash(data)
        h2 = compute_snapshot_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_returns_hex_sha256(self) -> None:
        h = compute_snapshot_hash({"x": 1})
        assert len(h) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# AuditWriter hash chain
# ---------------------------------------------------------------------------

class TestAuditWriter:
    def test_first_event_has_no_prev_hash(self) -> None:
        w = AuditWriter()
        evt = w.append(_make_event())
        assert evt.prev_event_hash is None
        assert evt.event_hash != ""

    def test_sequence_numbers_increment(self) -> None:
        w = AuditWriter()
        e1 = w.append(_make_event())
        e2 = w.append(_make_event())
        e3 = w.append(_make_event())
        assert e1.sequence_number == 1
        assert e2.sequence_number == 2
        assert e3.sequence_number == 3

    def test_hash_chain_links(self) -> None:
        w = AuditWriter()
        e1 = w.append(_make_event())
        e2 = w.append(_make_event())
        assert e2.prev_event_hash == e1.event_hash

    def test_event_hash_is_sha256(self) -> None:
        w = AuditWriter()
        evt = w.append(_make_event())
        assert len(evt.event_hash) == 64

    def test_hash_computation_matches_manual(self) -> None:
        w = AuditWriter()
        evt = w.append(_make_event(
            event_name="deploy.started",
            object_type="service",
            object_id="svc-1",
            correlation_id="corr-abc",
        ))
        expected = _compute_event_hash(
            sequence_number=1,
            event_name="deploy.started",
            object_type="service",
            object_id="svc-1",
            correlation_id="corr-abc",
            prev_event_hash=None,
        )
        assert evt.event_hash == expected

    def test_records_are_copies(self) -> None:
        w = AuditWriter()
        w.append(_make_event())
        records = w.records
        records.clear()
        assert len(w.records) == 1  # original untouched

    def test_append_only_no_mutation(self) -> None:
        """Records list grows; we never expose a delete/update method."""
        w = AuditWriter()
        w.append(_make_event())
        w.append(_make_event())
        assert len(w.records) == 2
        # AuditWriter has no delete or update method
        assert not hasattr(w, "delete")
        assert not hasattr(w, "update")


# ---------------------------------------------------------------------------
# AuditReader query
# ---------------------------------------------------------------------------

class TestAuditReader:
    def _populated_writer(self) -> AuditWriter:
        w = AuditWriter()
        w.append(_make_event(event_name="access.granted", actor_id="alice", object_type="role", object_id="r-1"))
        w.append(_make_event(event_name="deploy.started", actor_id="bob", object_type="service", object_id="svc-1"))
        w.append(_make_event(event_name="access.granted", actor_id="alice", object_type="role", object_id="r-2"))
        return w

    def test_query_all(self) -> None:
        r = AuditReader(self._populated_writer())
        assert len(r.query()) == 3

    def test_filter_by_actor(self) -> None:
        r = AuditReader(self._populated_writer())
        results = r.query(actor_id="alice")
        assert len(results) == 2

    def test_filter_by_event_name(self) -> None:
        r = AuditReader(self._populated_writer())
        results = r.query(event_name="deploy.started")
        assert len(results) == 1

    def test_filter_by_object_type(self) -> None:
        r = AuditReader(self._populated_writer())
        results = r.query(object_type="role")
        assert len(results) == 2

    def test_filter_by_object_id(self) -> None:
        r = AuditReader(self._populated_writer())
        results = r.query(object_id="r-1")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# AuditReader verify_chain
# ---------------------------------------------------------------------------

class TestAuditReaderVerifyChain:
    def test_valid_chain(self) -> None:
        w = AuditWriter()
        for _ in range(5):
            w.append(_make_event())
        r = AuditReader(w)
        assert r.verify_chain() is True

    def test_empty_chain_is_valid(self) -> None:
        r = AuditReader(AuditWriter())
        assert r.verify_chain() is True

    def test_tampered_hash_detected(self) -> None:
        w = AuditWriter()
        for _ in range(3):
            w.append(_make_event())
        # Tamper with the second record's hash
        w._records[1].event_hash = "0" * 64
        r = AuditReader(w)
        assert r.verify_chain() is False

    def test_tampered_prev_hash_detected(self) -> None:
        w = AuditWriter()
        for _ in range(3):
            w.append(_make_event())
        w._records[2].prev_event_hash = "f" * 64
        r = AuditReader(w)
        assert r.verify_chain() is False
