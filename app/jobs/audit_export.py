"""Audit export job — exports audit records for compliance.

Supports filtering and JSON format output.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.audit import AuditReader, AuditWriter, get_audit_log, record_audit_event
from app.core.ids import generate_correlation_id


async def export_audit_events(
    *,
    filters: dict[str, Any] | None = None,
    format: str = "json",
    writer: AuditWriter | None = None,
) -> dict[str, Any]:
    """Export audit records matching filters.

    Parameters
    ----------
    filters : dict
        Optional filters: event_name, actor_id, object_type, object_id,
        after (ISO datetime), before (ISO datetime).
    format : str
        Output format. Currently only "json" is supported.
    writer : AuditWriter
        If provided, uses AuditReader for structured queries.
        Otherwise falls back to the module-level audit log.
    """
    corr_id = generate_correlation_id()
    filters = filters or {}

    if writer is not None:
        reader = AuditReader(writer)
        query_kwargs: dict[str, Any] = {}
        if "actor_id" in filters:
            query_kwargs["actor_id"] = filters["actor_id"]
        if "event_name" in filters:
            query_kwargs["event_name"] = filters["event_name"]
        if "object_type" in filters:
            query_kwargs["object_type"] = filters["object_type"]
        if "object_id" in filters:
            query_kwargs["object_id"] = filters["object_id"]
        if "after" in filters:
            query_kwargs["after"] = datetime.fromisoformat(filters["after"])
        if "before" in filters:
            query_kwargs["before"] = datetime.fromisoformat(filters["before"])

        records = reader.query(**query_kwargs)
        exported = [r.model_dump(mode="json") for r in records]
    else:
        # Use module-level audit log
        raw_log = get_audit_log()
        exported = _apply_filters(raw_log, filters)

    # Record the export itself
    record_audit_event(
        event_name="audit.exported",
        actor_type="system",
        actor_id="audit_export",
        object_type="audit_export",
        object_id=corr_id,
        change_summary=f"Exported {len(exported)} audit records (format={format})",
        correlation_id=corr_id,
    )

    if format == "json":
        return {
            "format": "json",
            "count": len(exported),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "records": exported,
        }

    return {"format": format, "error": f"Unsupported format: {format}"}


def _apply_filters(
    records: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply dict-based filters to the module-level audit log."""
    results = list(records)

    if "event_name" in filters:
        results = [r for r in results if r.get("event_name") == filters["event_name"]]
    if "actor_id" in filters:
        results = [r for r in results if r.get("actor_id") == filters["actor_id"]]
    if "object_type" in filters:
        results = [r for r in results if r.get("object_type") == filters["object_type"]]
    if "object_id" in filters:
        results = [r for r in results if r.get("object_id") == filters["object_id"]]
    if "after" in filters:
        after_dt = filters["after"]
        results = [r for r in results if r.get("event_time", "") >= after_dt]
    if "before" in filters:
        before_dt = filters["before"]
        results = [r for r in results if r.get("event_time", "") <= before_dt]

    return results
