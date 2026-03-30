"""Tests for the Linear sync service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import CanonicalState, Priority
from app.jobs.linear_sync import (
    LinearSyncService,
    clear_stores,
    compute_sync_hash,
    get_links_store,
    get_reconciliation_tasks,
    map_priority_to_linear,
    map_state_to_linear,
)
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    clear_stores()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    clear_stores()
    clear_audit_log()
    clear_handlers()


def _mock_adapter(sync_result=None, webhook_result=None, search_result=None):
    """Create a mock LinearAdapter with configurable returns."""
    adapter = AsyncMock()
    adapter.execute = AsyncMock(side_effect=_make_execute_side_effect(
        sync_result, webhook_result, search_result,
    ))
    return adapter


def _make_execute_side_effect(sync_result, webhook_result, search_result):
    default_issue = {"id": "lin-123", "identifier": "DAT-1", "title": "Test", "state": {"name": "New"}}

    async def side_effect(action, payload):
        if action == "sync_work_item":
            return sync_result or {"success": True, "issue": default_issue}
        if action == "receive_webhook":
            return webhook_result or {
                "webhook_type": "Issue",
                "action": "update",
                "linear_id": "lin-123",
                "identifier": "DAT-1",
                "title": "Test",
                "state": None,
                "raw": {},
            }
        if action == "search_issue":
            return search_result or {"issues": [default_issue], "count": 1}
        if action == "create_project":
            return {"success": True, "project": {"id": "proj-lin-1", "name": "Test"}}
        return {}

    return side_effect


class TestSyncHash:
    def test_deterministic(self):
        data = {"title": "Test", "state": "new"}
        assert compute_sync_hash(data) == compute_sync_hash(data)

    def test_different_data_different_hash(self):
        h1 = compute_sync_hash({"title": "A"})
        h2 = compute_sync_hash({"title": "B"})
        assert h1 != h2

    def test_key_order_irrelevant(self):
        h1 = compute_sync_hash({"a": 1, "b": 2})
        h2 = compute_sync_hash({"b": 2, "a": 1})
        assert h1 == h2


class TestStateMapping:
    def test_map_state_to_linear(self):
        result = map_state_to_linear(CanonicalState.NEW)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_map_priority(self):
        result = map_priority_to_linear(Priority.HIGH)
        assert isinstance(result, int)


class TestSyncWorkItem:
    @pytest.mark.asyncio
    async def test_sync_creates_linear_issue(self):
        wi = await wi_service.create_work_item(title="Test sync")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)

        result = await svc.sync_work_item(wi.id)

        assert result["success"] is True
        assert result["linear_issue_id"] == "lin-123"
        assert wi.id in get_links_store()

    @pytest.mark.asyncio
    async def test_sync_is_idempotent(self):
        wi = await wi_service.create_work_item(title="Test idempotent")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)

        # First sync
        await svc.sync_work_item(wi.id)
        # Second sync — should be skipped (no changes)
        result = await svc.sync_work_item(wi.id)
        assert result["success"] is True
        assert result.get("skipped") is True

    @pytest.mark.asyncio
    async def test_sync_updates_after_change(self):
        wi = await wi_service.create_work_item(title="Test update")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)

        await svc.sync_work_item(wi.id)
        # Change the work item
        await wi_service.update_work_item(wi.id, actor="test", title="Updated title")
        # Sync again — should not be skipped
        result = await svc.sync_work_item(wi.id)
        assert result["success"] is True
        assert result.get("skipped") is not True

    @pytest.mark.asyncio
    async def test_sync_missing_work_item(self):
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.sync_work_item("nonexistent")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sync_emits_events(self):
        events: list[dict] = []
        subscribe("linear.sync_started", lambda e: events.append(e))
        subscribe("linear.sync_completed", lambda e: events.append(e))

        wi = await wi_service.create_work_item(title="Test events")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        event_names = {e.get("work_item_id") for e in events}
        assert wi.id in event_names

    @pytest.mark.asyncio
    async def test_sync_writes_audit(self):
        wi = await wi_service.create_work_item(title="Test audit")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        log = get_audit_log()
        assert any(r["event_name"] == "linear.sync_completed" for r in log)


class TestSyncProject:
    @pytest.mark.asyncio
    async def test_sync_project_creates(self):
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.sync_project("proj-1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_project_idempotent(self):
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        await svc.sync_project("proj-1")
        result = await svc.sync_project("proj-1")
        assert result.get("skipped") is True


class TestWebhookProcessing:
    @pytest.mark.asyncio
    async def test_webhook_applies_bidirectional_fields(self):
        wi = await wi_service.create_work_item(title="Test webhook")
        adapter = _mock_adapter(webhook_result={
            "webhook_type": "Issue",
            "action": "update",
            "linear_id": "lin-123",
            "state": None,
            "raw": {"assignee": {"name": "alice"}, "priority": 2},
        })
        svc = LinearSyncService(adapter)
        # First, create a link
        await svc.sync_work_item(wi.id)

        result = await svc.receive_webhook({
            "action": "update", "type": "Issue",
            "data": {"id": "lin-123"},
        })
        assert result["processed"] is True
        assert "owner_person_key" in result.get("updates_applied", [])

    @pytest.mark.asyncio
    async def test_webhook_rejects_state_change(self):
        wi = await wi_service.create_work_item(title="Test state reject")
        adapter = _mock_adapter(webhook_result={
            "webhook_type": "Issue",
            "action": "update",
            "linear_id": "lin-123",
            "state": "Done",
            "raw": {},
        })
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        result = await svc.receive_webhook({
            "action": "update", "type": "Issue",
            "data": {"id": "lin-123", "state": {"name": "Done"}},
        })
        assert result.get("reconciliation_created") is True
        assert len(get_reconciliation_tasks()) == 1

    @pytest.mark.asyncio
    async def test_webhook_unlinked_issue(self):
        adapter = _mock_adapter(webhook_result={
            "webhook_type": "Issue",
            "action": "update",
            "linear_id": "unknown-id",
            "state": None,
            "raw": {},
        })
        svc = LinearSyncService(adapter)
        result = await svc.receive_webhook({"action": "update", "type": "Issue", "data": {}})
        assert result["processed"] is False


class TestReconcile:
    @pytest.mark.asyncio
    async def test_reconcile_detects_conflict(self):
        wi = await wi_service.create_work_item(title="Test reconcile")
        # Mock search returns issue with different state
        mismatched_issue = {
            "id": "lin-123",
            "identifier": "DAT-1",
            "title": "Test reconcile",
            "state": {"name": "Done"},
        }
        adapter = _mock_adapter(search_result={"issues": [mismatched_issue], "count": 1})
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        result = await svc.reconcile(wi.id)
        assert result["success"] is True
        assert result["in_sync"] is False
        assert len(result["conflicts"]) > 0

    @pytest.mark.asyncio
    async def test_reconcile_no_link(self):
        wi = await wi_service.create_work_item(title="Test no link")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.reconcile(wi.id)
        assert result["success"] is False


class TestFullSync:
    @pytest.mark.asyncio
    async def test_full_sync_all_active(self):
        await wi_service.create_work_item(title="A")
        await wi_service.create_work_item(title="B")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)

        result = await svc.full_sync()
        assert result["total"] == 2
        assert result["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_full_sync_skips_done(self):
        wi = await wi_service.create_work_item(title="Done item")
        wi.canonical_state = CanonicalState.DONE
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)

        result = await svc.full_sync()
        assert result["total"] == 0


class TestSyncStatus:
    @pytest.mark.asyncio
    async def test_status_unsynced(self):
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        status = svc.get_sync_status("nonexistent")
        assert status["synced"] is False

    @pytest.mark.asyncio
    async def test_status_synced(self):
        wi = await wi_service.create_work_item(title="Status test")
        adapter = _mock_adapter()
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        status = svc.get_sync_status(wi.id)
        assert status["synced"] is True
        assert status["sync_hash"] is not None
