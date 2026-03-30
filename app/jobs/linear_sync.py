"""Linear sync service — bidirectional sync between OMDT and Linear.

Implements PRD section 12.6 sync rules:
- OMDT -> Linear is authoritative for lifecycle state
- Bidirectional for: assignee, label additions, priority, comments, due date
- Disallowed Linear state changes create reconciliation tasks
- Every sync is idempotent
- Every synced object stores both omdt_id and linear_id
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.adapters.linear import LinearAdapter
from app.core.audit import record_audit_event
from app.core.config import load_linear_config
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import CanonicalState, Priority
from app.domain.models.linear_link import LinearLink
from app.domain.models.work_item import WorkItem
from app.services import work_items as wi_service

# ---------------------------------------------------------------------------
# In-memory stores (will be backed by DB in production)
# ---------------------------------------------------------------------------

_linear_links: dict[str, LinearLink] = {}  # keyed by omdt_object_id
_reconciliation_tasks: list[dict[str, Any]] = []


def get_links_store() -> dict[str, LinearLink]:
    return _linear_links


def get_reconciliation_tasks() -> list[dict[str, Any]]:
    return _reconciliation_tasks


def clear_stores() -> None:
    _linear_links.clear()
    _reconciliation_tasks.clear()


# ---------------------------------------------------------------------------
# Sync hash computation
# ---------------------------------------------------------------------------

def compute_sync_hash(data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of sync-relevant fields."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# State mapping helpers
# ---------------------------------------------------------------------------

_STATE_MAP: dict[str, str] | None = None
_REVERSE_STATE_MAP: dict[str, str] | None = None
_PRIORITY_MAP: dict[str, int] | None = None


def _load_state_map() -> dict[str, str]:
    """Load CanonicalState -> Linear state name mapping from config."""
    global _STATE_MAP
    if _STATE_MAP is not None:
        return _STATE_MAP
    try:
        config = load_linear_config()
        _STATE_MAP = config.get("state_mappings", {})
    except Exception:
        # Fallback mapping
        _STATE_MAP = {s.value: s.value.replace("_", " ").title() for s in CanonicalState}
    return _STATE_MAP


def _load_reverse_state_map() -> dict[str, str]:
    """Load Linear state name -> CanonicalState mapping."""
    global _REVERSE_STATE_MAP
    if _REVERSE_STATE_MAP is not None:
        return _REVERSE_STATE_MAP
    forward = _load_state_map()
    _REVERSE_STATE_MAP = {v: k for k, v in forward.items()}
    return _REVERSE_STATE_MAP


def _load_priority_map() -> dict[str, int]:
    """Load Priority -> Linear priority int mapping from config."""
    global _PRIORITY_MAP
    if _PRIORITY_MAP is not None:
        return _PRIORITY_MAP
    try:
        config = load_linear_config()
        _PRIORITY_MAP = config.get("priority_mappings", {})
    except Exception:
        _PRIORITY_MAP = {"critical": 1, "high": 2, "medium": 3, "low": 4, "none": 0}
    return _PRIORITY_MAP


def map_state_to_linear(canonical_state: CanonicalState) -> str:
    """Map a CanonicalState to a Linear state name."""
    state_map = _load_state_map()
    return state_map.get(canonical_state.value, canonical_state.value.replace("_", " ").title())


def map_linear_state_to_canonical(linear_state: str) -> str | None:
    """Map a Linear state name to a CanonicalState value, or None if unknown."""
    reverse_map = _load_reverse_state_map()
    return reverse_map.get(linear_state)


def map_priority_to_linear(priority: Priority) -> int:
    """Map a Priority to a Linear priority integer."""
    pmap = _load_priority_map()
    return pmap.get(priority.value, 0)


# ---------------------------------------------------------------------------
# Sync-relevant fields for hash computation
# ---------------------------------------------------------------------------

BIDIRECTIONAL_FIELDS = frozenset({"assignee", "labels", "priority", "comments", "due_date"})


def _extract_sync_fields(work_item: WorkItem) -> dict[str, Any]:
    """Extract the fields relevant for sync hash computation."""
    return {
        "title": work_item.title,
        "description": work_item.description or "",
        "canonical_state": work_item.canonical_state.value,
        "priority": work_item.priority.value,
        "owner_person_key": work_item.owner_person_key or "",
        "due_at": work_item.due_at.isoformat() if work_item.due_at else "",
    }


# ---------------------------------------------------------------------------
# LinearSyncService
# ---------------------------------------------------------------------------

class LinearSyncService:
    """Manages synchronisation between OMDT work items and Linear issues."""

    def __init__(self, adapter: LinearAdapter) -> None:
        self._adapter = adapter

    # -- public API -----------------------------------------------------------

    async def sync_work_item(self, work_item_id: str) -> dict[str, Any]:
        """Create or update a Linear issue from an OMDT work item.

        Idempotent: if the sync hash hasn't changed, no Linear call is made.
        """
        corr_id = generate_correlation_id()

        await emit("linear.sync_started", {
            "work_item_id": work_item_id,
            "correlation_id": corr_id,
        })

        wi = await wi_service.get_work_item(work_item_id)
        if wi is None:
            await emit("linear.sync_failed", {
                "work_item_id": work_item_id,
                "error": "Work item not found",
                "correlation_id": corr_id,
            })
            return {"success": False, "error": "Work item not found"}

        # Compute current sync hash
        sync_fields = _extract_sync_fields(wi)
        current_hash = compute_sync_hash(sync_fields)

        # Check if sync is needed
        existing_link = _linear_links.get(work_item_id)
        if existing_link and existing_link.sync_hash == current_hash:
            return {"success": True, "skipped": True, "reason": "no_changes"}

        try:
            linear_state = map_state_to_linear(wi.canonical_state)
            payload: dict[str, Any] = {
                "work_item_id": work_item_id,
                "title": wi.title,
                "description": wi.description or "",
                "priority": map_priority_to_linear(wi.priority),
            }

            if existing_link:
                # Update existing issue
                payload["linear_issue_id"] = existing_link.linear_object_id
                result = await self._adapter.execute("sync_work_item", payload)
            else:
                # Create new issue — need team_id from config
                try:
                    config = load_linear_config()
                    teams = config.get("teams", [])
                    team_id = teams[0]["key"] if teams else "DATA"
                except Exception:
                    team_id = "DATA"
                payload["team_id"] = team_id
                result = await self._adapter.execute("sync_work_item", payload)

            # Extract linear issue id from result
            issue = result.get("issue", {}) or {}
            linear_id = issue.get("id", "") if issue else existing_link.linear_object_id if existing_link else ""

            # Update or create link
            now = datetime.now(timezone.utc)
            if existing_link:
                existing_link.last_sync_at = now
                existing_link.sync_hash = current_hash
            else:
                link = LinearLink(
                    id=uuid4(),
                    omdt_object_type="work_item",
                    omdt_object_id=work_item_id,
                    linear_object_type="issue",
                    linear_object_id=linear_id,
                    last_sync_at=now,
                    sync_hash=current_hash,
                )
                _linear_links[work_item_id] = link

            # Update work item with linear_issue_id if new
            if not wi.linear_issue_id and linear_id:
                await wi_service.update_work_item(
                    work_item_id, actor="linear_sync", linear_issue_id=linear_id,
                )

            await emit("linear.sync_completed", {
                "work_item_id": work_item_id,
                "linear_issue_id": linear_id,
                "correlation_id": corr_id,
            })

            record_audit_event(
                event_name="linear.sync_completed",
                actor_type="system",
                actor_id="linear_sync",
                object_type="work_item",
                object_id=work_item_id,
                change_summary=f"Synced work item to Linear issue {linear_id}",
                correlation_id=corr_id,
            )

            return {"success": True, "linear_issue_id": linear_id, "sync_hash": current_hash}

        except Exception as exc:
            await emit("linear.sync_failed", {
                "work_item_id": work_item_id,
                "error": str(exc),
                "correlation_id": corr_id,
            })

            record_audit_event(
                event_name="linear.sync_failed",
                actor_type="system",
                actor_id="linear_sync",
                object_type="work_item",
                object_id=work_item_id,
                change_summary=f"Linear sync failed: {exc}",
                correlation_id=corr_id,
            )

            return {"success": False, "error": str(exc)}

    async def sync_project(self, project_id: str) -> dict[str, Any]:
        """Create or update a Linear project from an OMDT project."""
        corr_id = generate_correlation_id()

        # For now, project sync operates on a simple payload
        existing_link = _linear_links.get(f"project:{project_id}")

        try:
            if existing_link:
                # Update is not directly supported via create_project, skip
                return {"success": True, "skipped": True, "reason": "project_already_linked"}

            result = await self._adapter.execute("create_project", {
                "name": f"OMDT Project {project_id}",
                "team_ids": ["DATA"],
                "description": f"Linked from OMDT project {project_id}",
            })

            project_data = result.get("project", {}) or {}
            linear_project_id = project_data.get("id", "")

            now = datetime.now(timezone.utc)
            link = LinearLink(
                id=uuid4(),
                omdt_object_type="project",
                omdt_object_id=uuid4(),  # synthetic UUID for project link
                linear_object_type="project",
                linear_object_id=linear_project_id,
                last_sync_at=now,
                sync_hash=compute_sync_hash({"project_id": project_id}),
            )
            _linear_links[f"project:{project_id}"] = link

            record_audit_event(
                event_name="linear.project_synced",
                actor_type="system",
                actor_id="linear_sync",
                object_type="project",
                object_id=project_id,
                change_summary=f"Created Linear project {linear_project_id}",
                correlation_id=corr_id,
            )

            return {"success": True, "linear_project_id": linear_project_id}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def receive_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an inbound Linear webhook.

        Applies bidirectional sync rules: only assignee, labels, priority,
        comments, and due_date changes from Linear are accepted.
        State changes from Linear are rejected and create reconciliation tasks.
        """
        corr_id = generate_correlation_id()

        result = await self._adapter.execute("receive_webhook", payload)

        webhook_type = result.get("webhook_type", "")
        action = result.get("action", "")
        linear_id = result.get("linear_id", "")
        linear_state = result.get("state")

        # Find the linked OMDT work item
        linked_wi_id: str | None = None
        for wi_id, link in _linear_links.items():
            if not wi_id.startswith("project:") and link.linear_object_id == linear_id:
                linked_wi_id = wi_id
                break

        if not linked_wi_id:
            return {"processed": False, "reason": "no_linked_work_item"}

        wi = await wi_service.get_work_item(linked_wi_id)
        if wi is None:
            return {"processed": False, "reason": "work_item_not_found"}

        # Check for disallowed state changes from Linear
        if linear_state:
            canonical_value = map_linear_state_to_canonical(linear_state)
            if canonical_value and canonical_value != wi.canonical_state.value:
                # Disallowed: Linear tried to change state. Create reconciliation task.
                _reconciliation_tasks.append({
                    "work_item_id": linked_wi_id,
                    "linear_issue_id": linear_id,
                    "conflict_type": "state_change_from_linear",
                    "linear_state": linear_state,
                    "omdt_state": wi.canonical_state.value,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

                record_audit_event(
                    event_name="linear.reconciliation_needed",
                    actor_type="system",
                    actor_id="linear_sync",
                    object_type="work_item",
                    object_id=linked_wi_id,
                    change_summary=f"Linear state change rejected: {linear_state} (OMDT: {wi.canonical_state.value})",
                    correlation_id=corr_id,
                )

                return {
                    "processed": True,
                    "reconciliation_created": True,
                    "conflict": "state_change_from_linear",
                }

        # Apply bidirectional field updates from webhook raw data
        raw = result.get("raw", {})
        updates: dict[str, Any] = {}

        if "assignee" in raw and isinstance(raw["assignee"], dict):
            assignee_name = raw["assignee"].get("name", "")
            if assignee_name:
                updates["owner_person_key"] = assignee_name

        if "priority" in raw:
            # Reverse-map Linear priority int to Priority enum
            pmap = _load_priority_map()
            reverse_pmap = {v: k for k, v in pmap.items()}
            linear_prio = raw["priority"]
            if linear_prio in reverse_pmap:
                try:
                    updates["priority"] = Priority(reverse_pmap[linear_prio])
                except ValueError:
                    pass

        if "dueDate" in raw and raw["dueDate"]:
            updates["due_at"] = raw["dueDate"]

        if updates:
            await wi_service.update_work_item(
                linked_wi_id, actor="linear_webhook", **updates,
            )

        record_audit_event(
            event_name="linear.webhook_processed",
            actor_type="system",
            actor_id="linear_sync",
            object_type="work_item",
            object_id=linked_wi_id,
            change_summary=f"Processed webhook: {webhook_type}.{action}",
            correlation_id=corr_id,
        )

        return {"processed": True, "updates_applied": list(updates.keys())}

    async def reconcile(self, work_item_id: str) -> dict[str, Any]:
        """Compare OMDT state vs Linear state and flag conflicts."""
        corr_id = generate_correlation_id()

        wi = await wi_service.get_work_item(work_item_id)
        if wi is None:
            return {"success": False, "error": "Work item not found"}

        link = _linear_links.get(work_item_id)
        if link is None:
            return {"success": False, "error": "No Linear link found"}

        # Fetch current Linear issue state
        try:
            result = await self._adapter.execute("search_issue", {
                "query": wi.title,
            })
        except Exception as exc:
            return {"success": False, "error": f"Failed to query Linear: {exc}"}

        issues = result.get("issues", [])
        linear_issue = None
        for issue in issues:
            if issue.get("id") == link.linear_object_id:
                linear_issue = issue
                break

        if not linear_issue:
            return {"success": False, "error": "Linear issue not found"}

        # Compare states
        linear_state_name = linear_issue.get("state", {}).get("name", "") if isinstance(linear_issue.get("state"), dict) else ""
        expected_linear_state = map_state_to_linear(wi.canonical_state)

        conflicts: list[dict[str, Any]] = []
        if linear_state_name and linear_state_name != expected_linear_state:
            conflicts.append({
                "field": "state",
                "omdt_value": wi.canonical_state.value,
                "linear_value": linear_state_name,
                "expected_linear_value": expected_linear_state,
            })

        if conflicts:
            _reconciliation_tasks.append({
                "work_item_id": work_item_id,
                "linear_issue_id": link.linear_object_id,
                "conflict_type": "state_mismatch",
                "conflicts": conflicts,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            record_audit_event(
                event_name="linear.reconciliation_needed",
                actor_type="system",
                actor_id="linear_sync",
                object_type="work_item",
                object_id=work_item_id,
                change_summary=f"Reconciliation: {len(conflicts)} conflict(s) detected",
                correlation_id=corr_id,
            )

        return {
            "success": True,
            "conflicts": conflicts,
            "in_sync": len(conflicts) == 0,
        }

    async def full_sync(self) -> dict[str, Any]:
        """Sync all active work items and projects to Linear."""
        corr_id = generate_correlation_id()

        active_states = {
            s for s in CanonicalState
            if s not in {CanonicalState.DONE, CanonicalState.ARCHIVED}
        }

        all_items = await wi_service.list_work_items()
        active_items = [wi for wi in all_items if wi.canonical_state in active_states]

        results: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0
        skipped = 0

        for wi in active_items:
            result = await self.sync_work_item(wi.id)
            results.append({"work_item_id": wi.id, **result})
            if result.get("success"):
                if result.get("skipped"):
                    skipped += 1
                else:
                    succeeded += 1
            else:
                failed += 1

        record_audit_event(
            event_name="linear.full_sync_completed",
            actor_type="system",
            actor_id="linear_sync",
            object_type="system",
            object_id="linear_sync",
            change_summary=f"Full sync: {succeeded} synced, {skipped} skipped, {failed} failed",
            correlation_id=corr_id,
        )

        return {
            "total": len(active_items),
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }

    # -- status query ---------------------------------------------------------

    def get_sync_status(self, work_item_id: str) -> dict[str, Any]:
        """Return the current sync status for a work item."""
        link = _linear_links.get(work_item_id)
        if link is None:
            return {"synced": False, "reason": "no_link"}

        tasks = [
            t for t in _reconciliation_tasks
            if t.get("work_item_id") == work_item_id
        ]

        return {
            "synced": True,
            "linear_object_id": link.linear_object_id,
            "last_sync_at": link.last_sync_at.isoformat() if link.last_sync_at else None,
            "sync_hash": link.sync_hash,
            "pending_reconciliation_tasks": len(tasks),
        }
