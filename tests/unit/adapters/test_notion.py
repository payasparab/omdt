"""Unit tests for the Notion adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.notion import NotionAdapter
from app.adapters.base import AdapterError
from tests.fixtures.notion_responses import (
    VALID_CONFIG,
    CREATE_PAGE_RESPONSE,
    UPDATE_PAGE_RESPONSE,
    GET_PAGE_RESPONSE,
)


@pytest.fixture
def adapter() -> NotionAdapter:
    return NotionAdapter(config=VALID_CONFIG.copy())


def _mock_api(response: dict[str, Any]):
    return patch.object(
        NotionAdapter, "_api_request", new_callable=AsyncMock, return_value=response
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid(self, adapter: NotionAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        a = NotionAdapter(config={})
        with pytest.raises(AdapterError, match="api_key"):
            await a.validate_config()


class TestCreatePage:
    @pytest.mark.asyncio
    async def test_creates_page(self, adapter: NotionAdapter):
        with _mock_api(CREATE_PAGE_RESPONSE):
            result = await adapter.execute(
                "create_page",
                {"parent_id": "db_01", "title": "Test PRD"},
            )
            assert result["created"] is True
            assert result["page_id"] == "page_01"

    @pytest.mark.asyncio
    async def test_create_page_missing_parent(self, adapter: NotionAdapter):
        with pytest.raises(AdapterError, match="parent_id"):
            await adapter.execute("create_page", {"title": "T"})

    @pytest.mark.asyncio
    async def test_create_page_missing_title(self, adapter: NotionAdapter):
        with pytest.raises(AdapterError, match="title"):
            await adapter.execute("create_page", {"parent_id": "db_01"})


class TestUpdatePage:
    @pytest.mark.asyncio
    async def test_updates_page(self, adapter: NotionAdapter):
        with _mock_api(UPDATE_PAGE_RESPONSE):
            result = await adapter.execute(
                "update_page",
                {"page_id": "page_01", "properties": {"Status": {"select": {"name": "In Review"}}}},
            )
            assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_update_page_missing_id(self, adapter: NotionAdapter):
        with pytest.raises(AdapterError, match="page_id"):
            await adapter.execute("update_page", {})


class TestGetPage:
    @pytest.mark.asyncio
    async def test_gets_page(self, adapter: NotionAdapter):
        with _mock_api(GET_PAGE_RESPONSE):
            result = await adapter.execute("get_page", {"page_id": "page_01"})
            assert result["page_id"] == "page_01"
            assert "properties" in result


class TestSyncPrd:
    @pytest.mark.asyncio
    async def test_sync_existing_updates(self, adapter: NotionAdapter):
        with _mock_api(UPDATE_PAGE_RESPONSE):
            result = await adapter.execute(
                "sync_prd",
                {"page_id": "page_01", "properties": {}},
            )
            assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_sync_new_creates(self, adapter: NotionAdapter):
        with _mock_api(CREATE_PAGE_RESPONSE):
            result = await adapter.execute(
                "sync_prd",
                {
                    "parent_id": "db_01",
                    "title": "New PRD",
                    "work_item_id": "wi_01",
                },
            )
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_sync_new_without_parent_fails(self, adapter: NotionAdapter):
        with pytest.raises(AdapterError, match="parent_id"):
            await adapter.execute("sync_prd", {"title": "T"})
