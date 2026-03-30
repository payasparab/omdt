"""Tests for the sync orchestrator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.events import DomainEvent, DomainEventNames, EventBus
from app.services.sync import SyncOrchestrator


@pytest.fixture
def bus():
    return EventBus()


def _mock_linear():
    svc = AsyncMock()
    svc.sync_work_item = AsyncMock(return_value={"success": True, "linear_issue_id": "lin-1"})
    return svc


def _mock_notion():
    svc = AsyncMock()
    svc.sync_prd = AsyncMock(return_value={"success": True, "page_id": "page-1"})
    return svc


class TestSubscription:
    def test_subscribe_all(self, bus):
        orch = SyncOrchestrator(bus, linear_sync_service=_mock_linear())
        orch.subscribe_all()

        assert bus.handler_count(DomainEventNames.WORK_ITEM_STATE_CHANGED) == 1
        assert bus.handler_count(DomainEventNames.WORK_ITEM_CREATED) == 1
        assert bus.handler_count(DomainEventNames.PRD_CREATED) == 1
        assert bus.handler_count(DomainEventNames.PRD_REVISED) == 1
        assert bus.handler_count(DomainEventNames.PRD_APPROVED) == 1

    def test_unsubscribe_all(self, bus):
        orch = SyncOrchestrator(bus, linear_sync_service=_mock_linear())
        orch.subscribe_all()
        orch.unsubscribe_all()

        assert bus.handler_count(DomainEventNames.WORK_ITEM_STATE_CHANGED) == 0


class TestOnWorkItemChange:
    @pytest.mark.asyncio
    async def test_triggers_linear_sync(self, bus):
        linear = _mock_linear()
        orch = SyncOrchestrator(bus, linear_sync_service=linear)

        result = await orch.on_work_item_change("wi-1")
        linear.sync_work_item.assert_called_once_with("wi-1")
        assert any(a["type"] == "linear_sync" for a in result["actions"])

    @pytest.mark.asyncio
    async def test_handles_linear_failure(self, bus):
        linear = AsyncMock()
        linear.sync_work_item = AsyncMock(side_effect=Exception("Connection error"))
        orch = SyncOrchestrator(bus, linear_sync_service=linear)

        result = await orch.on_work_item_change("wi-1")
        assert any("error" in a for a in result["actions"])

    @pytest.mark.asyncio
    async def test_no_services_does_nothing(self, bus):
        orch = SyncOrchestrator(bus)
        result = await orch.on_work_item_change("wi-1")
        assert result["actions"] == []


class TestOnPRDChange:
    @pytest.mark.asyncio
    async def test_triggers_notion_sync(self, bus):
        notion = _mock_notion()
        orch = SyncOrchestrator(bus, notion_sync_service=notion)

        result = await orch.on_prd_change("prd-1")
        notion.sync_prd.assert_called_once_with("prd-1")
        assert any(a["type"] == "notion_sync" for a in result["actions"])

    @pytest.mark.asyncio
    async def test_handles_notion_failure(self, bus):
        notion = AsyncMock()
        notion.sync_prd = AsyncMock(side_effect=Exception("API error"))
        orch = SyncOrchestrator(bus, notion_sync_service=notion)

        result = await orch.on_prd_change("prd-1")
        assert any("error" in a for a in result["actions"])


class TestOnFeedbackReceived:
    @pytest.mark.asyncio
    async def test_no_notification_service(self, bus):
        orch = SyncOrchestrator(bus)
        result = await orch.on_feedback_received("fb-1")
        assert result["actions"] == []


class TestEventDrivenIntegration:
    @pytest.mark.asyncio
    async def test_event_triggers_sync(self, bus):
        linear = _mock_linear()
        orch = SyncOrchestrator(bus, linear_sync_service=linear)
        orch.subscribe_all()

        event = DomainEvent(
            event_name=DomainEventNames.WORK_ITEM_STATE_CHANGED,
            actor_type="system",
            actor_id="test",
            object_type="work_item",
            object_id="wi-1",
            payload={"work_item_id": "wi-1", "from_state": "new", "to_state": "triage"},
        )
        await bus.emit(event)
        linear.sync_work_item.assert_called_once_with("wi-1")

    @pytest.mark.asyncio
    async def test_prd_event_triggers_notion(self, bus):
        notion = _mock_notion()
        orch = SyncOrchestrator(bus, notion_sync_service=notion)
        orch.subscribe_all()

        event = DomainEvent(
            event_name=DomainEventNames.PRD_CREATED,
            actor_type="agent",
            actor_id="data_pm",
            object_type="prd_revision",
            object_id="prd-1",
            payload={"prd_id": "prd-1", "work_item_id": "wi-1"},
        )
        await bus.emit(event)
        notion.sync_prd.assert_called_once_with("prd-1")


class TestSyncLog:
    @pytest.mark.asyncio
    async def test_log_records_actions(self, bus):
        orch = SyncOrchestrator(bus, linear_sync_service=_mock_linear())
        await orch.on_work_item_change("wi-1")
        await orch.on_work_item_change("wi-2")

        assert len(orch.sync_log) == 2

    def test_clear_log(self, bus):
        orch = SyncOrchestrator(bus)
        orch._sync_log.append({"test": True})
        orch.clear_log()
        assert len(orch.sync_log) == 0
