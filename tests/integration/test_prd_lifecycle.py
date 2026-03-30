"""Integration test: full PRD lifecycle.

Tests the complete flow: draft -> review -> feedback -> revision ->
approve -> frozen artifact -> Notion sync -> Linear update.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import CanonicalState, PRDStatus, SourceChannel
from app.jobs.linear_sync import LinearSyncService, clear_stores as clear_linear
from app.jobs.notion_sync import NotionSyncService, clear_stores as clear_notion
from app.services import conversations as conv_service
from app.services import feedback as fb_service
from app.services import prd as prd_service
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    prd_service.clear_stores()
    fb_service.clear_stores()
    conv_service.clear_stores()
    clear_linear()
    clear_notion()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    prd_service.clear_stores()
    fb_service.clear_stores()
    conv_service.clear_stores()
    clear_linear()
    clear_notion()
    clear_audit_log()
    clear_handlers()


def _mock_linear_adapter():
    adapter = AsyncMock()

    async def execute(action, payload):
        if action == "sync_work_item":
            return {"success": True, "issue": {"id": "lin-lifecycle", "identifier": "DAT-99", "title": "Test", "state": {"name": "New"}}}
        if action == "create_project":
            return {"success": True, "project": {"id": "proj-lin", "name": "Test"}}
        return {}

    adapter.execute = AsyncMock(side_effect=execute)
    return adapter


def _mock_notion_adapter():
    adapter = AsyncMock()
    _page_counter = {"n": 0}

    async def execute(action, payload):
        if action == "sync_prd":
            if payload.get("page_id"):
                return {"page_id": payload["page_id"], "url": "https://notion.so/updated", "updated": True}
            _page_counter["n"] += 1
            return {"page_id": f"notion-page-{_page_counter['n']}", "url": "https://notion.so/new", "created": True}
        if action == "update_page":
            return {"page_id": payload.get("page_id", ""), "url": "https://notion.so/updated", "updated": True}
        return {}

    adapter.execute = AsyncMock(side_effect=execute)
    return adapter


class TestFullPRDLifecycle:
    @pytest.mark.asyncio
    async def test_draft_to_approved_with_sync(self):
        """End-to-end: intake -> draft PRD -> review -> feedback ->
        revision -> approve -> Notion sync -> Linear sync."""

        # 1. Create work item and transition to PRD_DRAFTING
        wi = await wi_service.create_work_item(
            title="Build customer churn model",
            description="Need a churn prediction model",
            source_channel=SourceChannel.OUTLOOK,
            requester_person_key="stakeholder.jane",
        )
        await wi_service.transition_work_item(
            wi.id, CanonicalState.TRIAGE, "intake_service",
        )
        await wi_service.transition_work_item(
            wi.id, CanonicalState.READY_FOR_PRD, "triage_agent",
        )
        await wi_service.transition_work_item(
            wi.id, CanonicalState.PRD_DRAFTING, "data_pm",
        )

        # 2. Create PRD draft
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id,
            content="# Churn Model PRD\n## Goal\nPredict customer churn",
            author="data_pm",
        )
        assert prd.status == PRDStatus.DRAFT
        assert prd.revision_number == 1

        # 3. Submit for review
        fb_request = await prd_service.submit_for_review(prd.id)
        assert fb_request is not None
        assert prd.status == PRDStatus.IN_REVIEW

        # 4. Create feedback request and collect feedback
        feedback_req = await fb_service.create_feedback_request(
            work_item_id=wi.id,
            prd_id=wi.id,
            participants=["stakeholder.jane", "tech_lead.bob"],
            source_channel=SourceChannel.OUTLOOK,
        )
        fb_key = str(feedback_req.id)

        # Stakeholder provides feedback via conversation thread
        thread = await conv_service.create_thread(
            work_item_id=wi.id,
            source_channel=SourceChannel.OUTLOOK,
        )
        thread_id = str(thread.id)
        await conv_service.add_message(
            thread_id, "stakeholder.jane",
            "Need to add retention probability threshold",
            channel=SourceChannel.OUTLOOK,
        )
        await fb_service.record_feedback_response(
            fb_key, "stakeholder.jane",
            "Need retention threshold section",
            channel=SourceChannel.OUTLOOK,
        )

        # Tech lead responds
        await conv_service.add_message(
            thread_id, "tech_lead.bob",
            "Architecture looks solid, approve with minor changes",
            channel=SourceChannel.LINEAR,
        )
        await fb_service.record_feedback_response(
            fb_key, "tech_lead.bob",
            "LGTM with minor changes",
            channel=SourceChannel.LINEAR,
        )

        # All feedback collected
        assert feedback_req.status == "resolved"

        # 5. Incorporate feedback into revised PRD
        revised_prd = await prd_service.incorporate_feedback(
            prd.id,
            "Added retention probability threshold at 0.7",
        )
        assert revised_prd.revision_number == 2

        # 6. Approve the PRD
        approved = await prd_service.approve_prd(revised_prd.id, "head_of_data")
        assert approved.status == PRDStatus.APPROVED
        assert approved.is_frozen is True

        # 7. Sync to Notion
        notion_adapter = _mock_notion_adapter()
        notion_svc = NotionSyncService(notion_adapter, parent_db_id="db-123")
        notion_result = await notion_svc.sync_prd(revised_prd.id)
        assert notion_result["success"] is True

        # 8. Update work item and sync to Linear
        await wi_service.update_work_item(
            wi.id, actor="data_pm", latest_prd_revision_id=revised_prd.id,
        )
        linear_adapter = _mock_linear_adapter()
        linear_svc = LinearSyncService(linear_adapter)
        linear_result = await linear_svc.sync_work_item(wi.id)
        assert linear_result["success"] is True

        # Verify audit trail
        log = get_audit_log()
        event_names = [r["event_name"] for r in log]
        assert "prd.created" in event_names
        assert "prd.submitted_for_review" in event_names
        assert "prd.revised" in event_names
        assert "prd.approved" in event_names
        assert "notion.sync_completed" in event_names
        assert "linear.sync_completed" in event_names

    @pytest.mark.asyncio
    async def test_frozen_prd_cannot_be_revised(self):
        """Once approved, a PRD cannot be modified."""
        wi = await wi_service.create_work_item(title="Frozen test")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="Content", author="pm",
        )
        await prd_service.approve_prd(prd.id, "approver")

        # Attempt to revise frozen PRD
        result = await prd_service.incorporate_feedback(prd.id, "New feedback")
        assert result is None  # Cannot modify frozen PRD

    @pytest.mark.asyncio
    async def test_notion_sync_after_status_update(self):
        """Notion page status is updated when PRD status changes."""
        wi = await wi_service.create_work_item(title="Notion status")
        prd = await prd_service.create_prd_draft(
            work_item_id=wi.id, content="Content", author="pm",
        )

        notion_adapter = _mock_notion_adapter()
        notion_svc = NotionSyncService(notion_adapter, parent_db_id="db-123")

        # Create page
        await notion_svc.sync_prd(prd.id)

        # Update status
        result = await notion_svc.update_prd_status(prd.id, PRDStatus.IN_REVIEW)
        assert result["success"] is True
