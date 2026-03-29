"""Unit tests for the Outlook adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.outlook import OutlookAdapter
from app.adapters.base import AdapterError
from tests.fixtures.outlook_responses import (
    VALID_CONFIG,
    LIST_MESSAGES_RESPONSE,
)


@pytest.fixture
def adapter() -> OutlookAdapter:
    return OutlookAdapter(config=VALID_CONFIG.copy())


def _mock_graph(response: dict[str, Any]):
    return patch.object(
        OutlookAdapter, "_graph_request", new_callable=AsyncMock, return_value=response
    )


def _mock_token():
    return patch.object(
        OutlookAdapter, "_get_access_token", new_callable=AsyncMock, return_value="fake_token"
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid(self, adapter: OutlookAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_fields(self):
        a = OutlookAdapter(config={})
        with pytest.raises(AdapterError, match="missing required fields"):
            await a.validate_config()


class TestIngestMessages:
    @pytest.mark.asyncio
    async def test_ingests_messages(self, adapter: OutlookAdapter):
        with _mock_graph(LIST_MESSAGES_RESPONSE):
            result = await adapter.execute("ingest_messages", {})
            assert result["count"] == 2
            msg = result["messages"][0]
            assert msg["subject"] == "Data request"
            assert msg["from"] == "user@example.com"
            assert msg["conversation_id"] == "conv_01"

    @pytest.mark.asyncio
    async def test_thread_preservation(self, adapter: OutlookAdapter):
        with _mock_graph(LIST_MESSAGES_RESPONSE):
            result = await adapter.execute("ingest_messages", {})
            ids = [m["conversation_id"] for m in result["messages"]]
            assert ids == ["conv_01", "conv_01"]  # same thread


class TestReplyInThread:
    @pytest.mark.asyncio
    async def test_replies(self, adapter: OutlookAdapter):
        with _mock_graph({"status": "ok"}):
            result = await adapter.execute(
                "reply_in_thread",
                {"message_id": "msg_01", "body": "Got it!"},
            )
            assert result["replied"] is True

    @pytest.mark.asyncio
    async def test_reply_missing_message_id(self, adapter: OutlookAdapter):
        with pytest.raises(AdapterError, match="message_id"):
            await adapter.execute("reply_in_thread", {"body": "hi"})


class TestSendOutbound:
    @pytest.mark.asyncio
    async def test_sends(self, adapter: OutlookAdapter):
        with _mock_graph({"status": "ok"}):
            result = await adapter.execute(
                "send_outbound",
                {
                    "to": ["user@example.com"],
                    "subject": "Update",
                    "body": "<p>Status update</p>",
                },
            )
            assert result["sent"] is True

    @pytest.mark.asyncio
    async def test_send_missing_fields(self, adapter: OutlookAdapter):
        with pytest.raises(AdapterError, match="requires"):
            await adapter.execute("send_outbound", {"to": ["a@b.com"]})


class TestListInbox:
    @pytest.mark.asyncio
    async def test_list_inbox(self, adapter: OutlookAdapter):
        response = {
            "value": [
                {
                    "id": "msg_01",
                    "subject": "Hello",
                    "from": {"emailAddress": {"address": "a@b.com"}},
                    "receivedDateTime": "2026-03-29T08:00:00Z",
                    "isRead": False,
                }
            ]
        }
        with _mock_graph(response):
            result = await adapter.execute("list_inbox", {})
            assert result["count"] == 1
            assert result["messages"][0]["subject"] == "Hello"
