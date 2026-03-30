"""Integration test: email -> intake -> triage -> work item -> Linear -> audit trail."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import CanonicalState, SourceChannel, WorkItemType
from app.services import intake, work_items
from app.services.work_items import get_work_item


@pytest.fixture(autouse=True)
def _clean():
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()


class TestIntakePipeline:
    """Email arrives -> intake normalizes -> triage classifies -> work item created -> audit trail complete."""

    @pytest.mark.asyncio
    async def test_email_intake_creates_work_item_in_triage(self) -> None:
        """Full intake pipeline from email to TRIAGE state."""
        wi = await intake.process_intake(
            message="Dashboard request\nNeed a new executive dashboard for Q1 metrics",
            source_channel=SourceChannel.EMAIL,
            requester="alice@example.com",
            external_id="msg-001",
        )

        assert wi is not None
        assert wi.title == "Dashboard request"
        assert wi.source_channel == SourceChannel.EMAIL
        assert wi.requester_person_key == "alice@example.com"
        assert wi.source_external_id == "msg-001"
        # After intake, work item should be in TRIAGE
        assert wi.canonical_state == CanonicalState.TRIAGE

    @pytest.mark.asyncio
    async def test_intake_emits_events(self) -> None:
        """Verify intake.received and intake.normalized events are emitted."""
        received_events: list[dict] = []
        normalized_events: list[dict] = []

        subscribe("intake.received", lambda p: received_events.append(p))
        subscribe("intake.normalized", lambda p: normalized_events.append(p))

        await intake.process_intake(
            message="Pipeline fix\nThe ETL pipeline is broken",
            source_channel=SourceChannel.OUTLOOK,
            requester="bob@example.com",
        )

        assert len(received_events) == 1
        assert received_events[0]["source_channel"] == "outlook"
        assert len(normalized_events) == 1
        assert "work_item_id" in normalized_events[0]

    @pytest.mark.asyncio
    async def test_intake_creates_audit_trail(self) -> None:
        """Verify full audit trail: work_item.created + intake.normalized + state_changed."""
        await intake.process_intake(
            message="Access request\nNeed Snowflake access for analytics",
            source_channel=SourceChannel.API,
            requester="carol@example.com",
        )

        audit = get_audit_log()
        event_names = [r["event_name"] for r in audit]
        # Must have: work_item.created, intake.normalized, work_item.state_changed (NEW->TRIAGE)
        assert "work_item.created" in event_names
        assert "intake.normalized" in event_names
        assert "work_item.state_changed" in event_names

    @pytest.mark.asyncio
    async def test_intake_work_item_persisted_in_store(self) -> None:
        """Verify the work item is retrievable after intake."""
        wi = await intake.process_intake(
            message="Bug report\nData mismatch in revenue dashboard",
            source_channel=SourceChannel.LINEAR,
            requester="dave@example.com",
            external_id="LIN-456",
        )

        retrieved = await get_work_item(wi.id)
        assert retrieved is not None
        assert retrieved.id == wi.id
        assert retrieved.canonical_state == CanonicalState.TRIAGE

    @pytest.mark.asyncio
    async def test_intake_metadata_preserved(self) -> None:
        """Verify metadata dict is preserved through intake."""
        wi = await intake.process_intake(
            message="Report request\nMonthly financials",
            source_channel=SourceChannel.API,
            metadata={"urgency": "high", "department": "finance"},
        )

        assert wi.metadata.get("urgency") == "high"
        assert wi.metadata.get("department") == "finance"

    @pytest.mark.asyncio
    async def test_multiple_intakes_create_separate_items(self) -> None:
        """Multiple intake messages create distinct work items."""
        wi1 = await intake.process_intake(message="Request one", source_channel=SourceChannel.API)
        wi2 = await intake.process_intake(message="Request two", source_channel=SourceChannel.API)

        assert wi1.id != wi2.id
        assert len(work_items.get_store()) == 2
