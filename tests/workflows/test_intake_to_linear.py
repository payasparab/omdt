"""Workflow test: intake -> triage -> work item -> Linear issue.

Tests the end-to-end flow from intake through triage to Linear sync.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import CanonicalState, SourceChannel
from app.jobs.linear_sync import LinearSyncService, clear_stores as clear_linear, get_links_store
from app.services import work_items as wi_service
from app.services.intake import process_intake


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    clear_linear()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    clear_linear()
    clear_audit_log()
    clear_handlers()


def _mock_linear_adapter():
    adapter = AsyncMock()

    async def execute(action, payload):
        if action == "sync_work_item":
            return {
                "success": True,
                "issue": {
                    "id": "lin-intake-1",
                    "identifier": "DAT-101",
                    "title": payload.get("title", ""),
                    "state": {"name": "New"},
                },
            }
        return {}

    adapter.execute = AsyncMock(side_effect=execute)
    return adapter


class TestIntakeToLinear:
    @pytest.mark.asyncio
    async def test_full_intake_to_linear_flow(self):
        """Intake message -> work item (state: TRIAGE) -> Linear issue."""

        # 1. Process intake
        wi = await process_intake(
            message="Build a churn dashboard\nNeed a dashboard showing customer churn metrics",
            source_channel=SourceChannel.OUTLOOK,
            requester="stakeholder@example.com",
            external_id="outlook-msg-456",
        )

        # Intake transitions to TRIAGE
        assert wi.canonical_state == CanonicalState.TRIAGE
        assert wi.title == "Build a churn dashboard"
        assert wi.source_channel == SourceChannel.OUTLOOK

        # 2. Simulate triage routing (sets route_key)
        await wi_service.update_work_item(
            wi.id,
            actor="triage_agent",
            route_key="analysis_request",
        )

        # 3. Transition through states toward READY_FOR_BUILD
        await wi_service.transition_work_item(
            wi.id, CanonicalState.READY_FOR_PRD, "triage_agent", "Routing complete",
        )

        # 4. Sync to Linear
        adapter = _mock_linear_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.sync_work_item(wi.id)

        assert result["success"] is True
        assert result["linear_issue_id"] == "lin-intake-1"

        # Verify link stored
        links = get_links_store()
        assert wi.id in links
        assert links[wi.id].linear_object_id == "lin-intake-1"

        # Verify work item updated with linear_issue_id
        updated_wi = await wi_service.get_work_item(wi.id)
        assert updated_wi.linear_issue_id == "lin-intake-1"

    @pytest.mark.asyncio
    async def test_intake_audit_trail(self):
        """Verify audit trail from intake through Linear sync."""
        wi = await process_intake(
            message="Urgent: fix data pipeline\nPipeline X is failing",
            source_channel=SourceChannel.EMAIL,
            requester="ops@example.com",
        )

        adapter = _mock_linear_adapter()
        svc = LinearSyncService(adapter)
        await svc.sync_work_item(wi.id)

        log = get_audit_log()
        event_names = [r["event_name"] for r in log]

        # Should have intake, state change, and sync events
        assert "intake.normalized" in event_names
        assert "work_item.created" in event_names
        assert "work_item.state_changed" in event_names
        assert "linear.sync_completed" in event_names

    @pytest.mark.asyncio
    async def test_cli_intake_to_linear(self):
        """CLI intake also flows to Linear."""
        wi = await process_intake(
            message="Add retention metric to dashboard",
            source_channel=SourceChannel.CLI,
            requester="payas.parab",
        )

        assert wi.source_channel == SourceChannel.CLI

        adapter = _mock_linear_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.sync_work_item(wi.id)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_after_multiple_state_transitions(self):
        """Sync updates reflect the latest state after multiple transitions."""
        wi = await process_intake(
            message="New analysis request",
            source_channel=SourceChannel.API,
        )

        # Further transitions
        await wi_service.transition_work_item(
            wi.id, CanonicalState.READY_FOR_PRD, "triage_agent",
        )
        await wi_service.transition_work_item(
            wi.id, CanonicalState.PRD_DRAFTING, "data_pm",
        )

        adapter = _mock_linear_adapter()
        svc = LinearSyncService(adapter)
        result = await svc.sync_work_item(wi.id)
        assert result["success"] is True

        # Sync again after another state change — should update
        await wi_service.transition_work_item(
            wi.id, CanonicalState.PRD_REVIEW, "data_pm",
        )
        result2 = await svc.sync_work_item(wi.id)
        assert result2["success"] is True
        assert result2.get("skipped") is not True  # state changed
