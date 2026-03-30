"""Tests for the Notion sync service."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import PRDStatus
from app.jobs.notion_sync import NotionSyncService, clear_stores, get_page_links
from app.services import prd as prd_service
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    prd_service.clear_stores()
    clear_stores()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    prd_service.clear_stores()
    clear_stores()
    clear_audit_log()
    clear_handlers()


def _mock_adapter():
    adapter = AsyncMock()

    async def execute(action, payload):
        if action == "sync_prd":
            if payload.get("page_id"):
                return {"page_id": payload["page_id"], "url": "https://notion.so/updated", "updated": True}
            return {"page_id": "notion-page-1", "url": "https://notion.so/new", "created": True}
        if action == "update_page":
            return {"page_id": payload.get("page_id", ""), "url": "https://notion.so/updated", "updated": True}
        return {}

    adapter.execute = AsyncMock(side_effect=execute)
    return adapter


class TestSyncPRD:
    @pytest.mark.asyncio
    async def test_creates_notion_page(self):
        wi = await wi_service.create_work_item(title="PRD test")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="# Overview\nThis is a test PRD", author="alice",
        )

        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")

        result = await svc.sync_prd(prd.id)
        assert result["success"] is True
        assert prd.id in get_page_links()

    @pytest.mark.asyncio
    async def test_updates_existing_page(self):
        wi = await wi_service.create_work_item(title="PRD update")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="Content", author="alice",
        )

        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")

        # First sync creates
        await svc.sync_prd(prd.id)
        # Second sync updates
        result = await svc.sync_prd(prd.id)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_missing_prd(self):
        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")
        result = await svc.sync_prd("nonexistent")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sync_emits_audit(self):
        wi = await wi_service.create_work_item(title="Audit test")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="Content", author="alice",
        )

        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")
        await svc.sync_prd(prd.id)

        log = get_audit_log()
        assert any(r["event_name"] == "notion.sync_completed" for r in log)


class TestUpdatePRDStatus:
    @pytest.mark.asyncio
    async def test_update_status(self):
        wi = await wi_service.create_work_item(title="Status test")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="Content", author="alice",
        )

        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")
        # Create the page first
        await svc.sync_prd(prd.id)

        result = await svc.update_prd_status(prd.id, PRDStatus.IN_REVIEW)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_status_no_page(self):
        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")
        result = await svc.update_prd_status("no-page", PRDStatus.DRAFT)
        assert result["success"] is False


class TestAttachArtifact:
    @pytest.mark.asyncio
    async def test_attach_artifact(self):
        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")

        result = await svc.attach_artifact("notion-page-1", {
            "artifact_type": "prd",
            "version": "1.0",
            "storage_uri": "s3://bucket/prd-v1.md",
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_attach_artifact_emits_audit(self):
        adapter = _mock_adapter()
        svc = NotionSyncService(adapter, parent_db_id="db-123")

        await svc.attach_artifact("notion-page-1", {
            "artifact_type": "prd",
            "version": "1.0",
            "storage_uri": "s3://bucket/prd-v1.md",
        })

        log = get_audit_log()
        assert any(r["event_name"] == "notion.artifact_attached" for r in log)
