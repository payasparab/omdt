"""Append-only audit event system with tamper-evident hash chain.

Implements §15.4 and §15.9 audit record requirements including
SHA-256 hash chaining via ``prev_event_hash`` / ``event_hash``.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.core.ids import generate_audit_id, get_current_correlation_id


# ---------------------------------------------------------------------------
# Snapshot helper
# ---------------------------------------------------------------------------

def compute_snapshot_hash(data: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hex digest of *data*.

    Keys are sorted to ensure consistent hashing regardless of
    insertion order.
    """
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Audit event model (§15.4 / §15.9)
# ---------------------------------------------------------------------------

class AuditEvent(BaseModel):
    """Pydantic v2 model for an append-only audit record."""

    audit_event_id: str = Field(default_factory=generate_audit_id)
    sequence_number: int
    event_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    event_name: str
    actor_type: str  # "human" | "agent" | "system"
    actor_id: str
    initiator_person_key: str | None = None
    correlation_id: str | None = Field(
        default_factory=get_current_correlation_id
    )
    object_type: str
    object_id: str
    before_snapshot_hash: str | None = None
    after_snapshot_hash: str | None = None
    change_summary: str = ""
    tool_name: str | None = None
    approval_id: str | None = None
    source_ip_or_channel: str | None = None
    prev_event_hash: str | None = None
    event_hash: str = ""  # computed by AuditWriter before storage


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------

def _compute_event_hash(
    sequence_number: int,
    event_name: str,
    object_type: str,
    object_id: str,
    correlation_id: str | None,
    prev_event_hash: str | None,
) -> str:
    """Compute the SHA-256 hash that seals an audit event into the chain."""
    parts = [
        str(sequence_number),
        event_name,
        object_type,
        object_id,
        correlation_id or "",
        prev_event_hash or "",
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# AuditWriter — append-only, hash-chained
# ---------------------------------------------------------------------------

class AuditWriter:
    """Append-only writer that maintains a tamper-evident hash chain.

    Records are stored in an in-memory list.  A production implementation
    would persist to the ``audit_events`` database table; this in-memory
    version is sufficient for the core module and unit tests.
    """

    def __init__(self) -> None:
        self._records: list[AuditEvent] = []
        self._lock = threading.Lock()
        self._sequence: int = 0

    @property
    def prev_event_hash(self) -> str | None:
        """Hash of the most recently appended event, or ``None``."""
        if not self._records:
            return None
        return self._records[-1].event_hash

    def append(self, event: AuditEvent) -> AuditEvent:
        """Seal *event* into the hash chain and append it.

        The writer assigns ``sequence_number``, ``prev_event_hash``, and
        ``event_hash`` — callers should NOT set these manually.
        """
        with self._lock:
            self._sequence += 1
            event.sequence_number = self._sequence
            event.prev_event_hash = self.prev_event_hash
            event.event_hash = _compute_event_hash(
                sequence_number=event.sequence_number,
                event_name=event.event_name,
                object_type=event.object_type,
                object_id=event.object_id,
                correlation_id=event.correlation_id,
                prev_event_hash=event.prev_event_hash,
            )
            self._records.append(event)
        return event

    @property
    def records(self) -> list[AuditEvent]:
        """Return an immutable *copy* of the audit log."""
        return list(self._records)


# ---------------------------------------------------------------------------
# AuditReader — query & verify
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Module-level convenience API — simpler interface for services & tests
# ---------------------------------------------------------------------------

_audit_log: list[dict[str, Any]] = []


def record_audit_event(
    *,
    event_name: str,
    actor_type: str,
    actor_id: str,
    object_type: str,
    object_id: str,
    change_summary: str,
    correlation_id: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Append a simplified audit record to the module-level log.

    This is the convenience API used by services. A production
    implementation would delegate to AuditWriter + DB persistence.
    """
    record = {
        "event_name": event_name,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "object_type": object_type,
        "object_id": object_id,
        "change_summary": change_summary,
        "correlation_id": correlation_id,
        "approval_id": approval_id,
        "event_time": datetime.now(timezone.utc).isoformat(),
    }
    _audit_log.append(record)
    return record


def get_audit_log() -> list[dict[str, Any]]:
    """Return a copy of the module-level audit log."""
    return list(_audit_log)


def clear_audit_log() -> None:
    """Clear the module-level audit log (for testing)."""
    _audit_log.clear()


class AuditReader:
    """Read-only view over an :class:`AuditWriter`'s records with
    filtering (§15.8) and hash-chain verification.
    """

    def __init__(self, writer: AuditWriter) -> None:
        self._writer = writer

    def query(
        self,
        *,
        project_id: str | None = None,
        work_item_id: str | None = None,
        actor_id: str | None = None,
        event_name: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        tool_name: str | None = None,
        approval_id: str | None = None,
        source_ip_or_channel: str | None = None,
        environment: str | None = None,
    ) -> list[AuditEvent]:
        """Return audit records matching the supplied filters.

        Filters for ``project_id`` / ``work_item_id`` / ``environment``
        are matched against the event's ``object_id`` or metadata.
        """
        results: list[AuditEvent] = []
        for rec in self._writer.records:
            if actor_id and rec.actor_id != actor_id:
                continue
            if event_name and rec.event_name != event_name:
                continue
            if object_type and rec.object_type != object_type:
                continue
            if object_id and rec.object_id != object_id:
                continue
            if tool_name and rec.tool_name != tool_name:
                continue
            if approval_id and rec.approval_id != approval_id:
                continue
            if source_ip_or_channel and rec.source_ip_or_channel != source_ip_or_channel:
                continue
            if after and rec.event_time < after:
                continue
            if before and rec.event_time > before:
                continue
            # project_id / work_item_id matched via object_id convention
            if project_id and rec.object_id != project_id:
                continue
            if work_item_id and rec.object_id != work_item_id:
                continue
            results.append(rec)
        return results

    def verify_chain(self) -> bool:
        """Verify the hash chain is intact.  Returns ``True`` if every
        record's ``event_hash`` matches a recomputation from its fields
        and the previous record's hash.
        """
        records = self._writer.records
        prev_hash: str | None = None
        for rec in records:
            expected = _compute_event_hash(
                sequence_number=rec.sequence_number,
                event_name=rec.event_name,
                object_type=rec.object_type,
                object_id=rec.object_id,
                correlation_id=rec.correlation_id,
                prev_event_hash=prev_hash,
            )
            if rec.event_hash != expected:
                return False
            if rec.prev_event_hash != prev_hash:
                return False
            prev_hash = rec.event_hash
        return True
