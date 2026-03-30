"""Tests for the notification dispatch job."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.jobs.notification_dispatch import (
    clear_sent_log,
    dispatch_notification,
    dispatch_to_group,
    get_sent_log,
)


@pytest.fixture(autouse=True)
def _clean():
    clear_sent_log()
    clear_audit_log()
    clear_handlers()
    yield
    clear_sent_log()
    clear_audit_log()
    clear_handlers()


def _mock_adapters():
    outlook = AsyncMock()
    outlook.execute = AsyncMock(return_value={"sent": True})
    linear = AsyncMock()
    linear.execute = AsyncMock(return_value={"success": True})
    notion = AsyncMock()
    notion.execute = AsyncMock(return_value={"updated": True})
    return {"outlook": outlook, "linear": linear, "notion": notion}


class TestDispatchNotification:
    @pytest.mark.asyncio
    async def test_dispatch_email(self):
        adapters = _mock_adapters()
        result = await dispatch_notification(
            recipient="alice@example.com",
            channel="email",
            subject="Test",
            body="Hello",
            adapters=adapters,
        )
        assert result["success"] is True
        assert result["sent"] is True
        adapters["outlook"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_linear_comment(self):
        adapters = _mock_adapters()
        result = await dispatch_notification(
            recipient="user-1",
            channel="linear",
            subject="Update",
            body="Status changed",
            context={"linear_issue_id": "issue-1"},
            adapters=adapters,
        )
        assert result["success"] is True
        adapters["linear"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_notion(self):
        adapters = _mock_adapters()
        result = await dispatch_notification(
            recipient="page-owner",
            channel="notion",
            subject="PRD Updated",
            body="New revision",
            context={"notion_page_id": "page-1"},
            adapters=adapters,
        )
        assert result["success"] is True
        adapters["notion"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_dry_run_no_adapters(self):
        result = await dispatch_notification(
            recipient="alice@example.com",
            channel="email",
            subject="Test",
            body="Hello",
        )
        assert result["success"] is True
        assert result.get("dry_run") is True

    @pytest.mark.asyncio
    async def test_dispatch_logs_sent(self):
        adapters = _mock_adapters()
        await dispatch_notification(
            recipient="alice@example.com",
            channel="email",
            subject="Test",
            body="Hello",
            adapters=adapters,
        )
        log = get_sent_log()
        assert len(log) == 1
        assert log[0]["recipient"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_dispatch_writes_audit(self):
        await dispatch_notification(
            recipient="alice@example.com",
            channel="email",
            subject="Test",
            body="Hello",
        )
        log = get_audit_log()
        assert any(r["event_name"] == "notification.dispatched" for r in log)


class TestFallbackLogic:
    @pytest.mark.asyncio
    async def test_linear_without_issue_id(self):
        """Linear dispatch without issue_id should not crash."""
        adapters = _mock_adapters()
        result = await dispatch_notification(
            recipient="user-1",
            channel="linear",
            subject="Test",
            body="Hello",
            context={},  # no linear_issue_id
            adapters=adapters,
        )
        assert result["success"] is True
        assert result["sent"] is False  # no issue_id to comment on

    @pytest.mark.asyncio
    async def test_notion_without_page_id(self):
        adapters = _mock_adapters()
        result = await dispatch_notification(
            recipient="owner",
            channel="notion",
            subject="Test",
            body="Hello",
            context={},  # no notion_page_id
            adapters=adapters,
        )
        assert result["success"] is True
        assert result["sent"] is False


class TestBatchDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_to_group(self):
        adapters = _mock_adapters()
        results = await dispatch_to_group(
            recipients=["alice@example.com", "bob@example.com"],
            channel="email",
            subject="Group test",
            body="Hello all",
            adapters=adapters,
        )
        assert len(results) == 2
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_dispatch_handles_partial_failure(self):
        """One adapter failure shouldn't crash the batch."""
        outlook = AsyncMock()
        call_count = 0

        async def flaky_execute(action, payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return {"sent": True}

        outlook.execute = AsyncMock(side_effect=flaky_execute)
        adapters = {"outlook": outlook}

        results = await dispatch_to_group(
            recipients=["alice@example.com", "bob@example.com"],
            channel="email",
            subject="Test",
            body="Hello",
            adapters=adapters,
        )
        assert len(results) == 2
        assert results[0]["success"] is False
        assert results[1]["success"] is True
