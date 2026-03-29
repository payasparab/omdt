"""Tests for the work items service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import CanonicalState, Priority, WorkItemType
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestCreateWorkItem:
    @pytest.mark.asyncio
    async def test_create_returns_work_item(self):
        wi = await wi_service.create_work_item(title="Test", description="desc")
        assert wi.title == "Test"
        assert wi.canonical_state == CanonicalState.NEW

    @pytest.mark.asyncio
    async def test_create_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("work_item.created", handler)

        await wi_service.create_work_item(title="Test")
        assert len(events) == 1
        assert events[0]["title"] == "Test"

    @pytest.mark.asyncio
    async def test_create_writes_audit(self):
        await wi_service.create_work_item(title="Test")
        log = get_audit_log()
        assert any(r["event_name"] == "work_item.created" for r in log)


class TestGetWorkItem:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        wi = await wi_service.create_work_item(title="Test")
        found = await wi_service.get_work_item(wi.id)
        assert found is not None
        assert found.id == wi.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        assert await wi_service.get_work_item("nonexistent") is None


class TestListWorkItems:
    @pytest.mark.asyncio
    async def test_list_all(self):
        await wi_service.create_work_item(title="A")
        await wi_service.create_work_item(title="B")
        items = await wi_service.list_work_items()
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_state(self):
        await wi_service.create_work_item(title="A")
        items = await wi_service.list_work_items(state=CanonicalState.NEW)
        assert len(items) == 1
        items = await wi_service.list_work_items(state=CanonicalState.TRIAGE)
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        await wi_service.create_work_item(title="A", work_type=WorkItemType.BUG)
        await wi_service.create_work_item(title="B", work_type=WorkItemType.TASK)
        items = await wi_service.list_work_items(work_type=WorkItemType.BUG)
        assert len(items) == 1


class TestUpdateWorkItem:
    @pytest.mark.asyncio
    async def test_update_fields(self):
        wi = await wi_service.create_work_item(title="Old")
        updated = await wi_service.update_work_item(wi.id, actor="user1", title="New")
        assert updated.title == "New"

    @pytest.mark.asyncio
    async def test_update_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("work_item.updated", handler)

        wi = await wi_service.create_work_item(title="Old")
        await wi_service.update_work_item(wi.id, actor="user1", title="New")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_update_does_not_change_state(self):
        wi = await wi_service.create_work_item(title="T")
        await wi_service.update_work_item(
            wi.id, actor="user1", canonical_state=CanonicalState.DONE
        )
        found = await wi_service.get_work_item(wi.id)
        assert found.canonical_state == CanonicalState.NEW  # unchanged

    @pytest.mark.asyncio
    async def test_update_missing_returns_none(self):
        result = await wi_service.update_work_item("nope", actor="user1", title="X")
        assert result is None


class TestTransitionWorkItem:
    @pytest.mark.asyncio
    async def test_transition_succeeds(self):
        wi = await wi_service.create_work_item(title="T")
        result = await wi_service.transition_work_item(
            wi.id, CanonicalState.TRIAGE, "user1"
        )
        assert result.success is True
        found = await wi_service.get_work_item(wi.id)
        assert found.canonical_state == CanonicalState.TRIAGE

    @pytest.mark.asyncio
    async def test_transition_missing_item_fails(self):
        result = await wi_service.transition_work_item(
            "nonexistent", CanonicalState.TRIAGE, "user1"
        )
        assert result.success is False
