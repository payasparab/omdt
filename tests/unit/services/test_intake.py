"""Tests for the intake service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import CanonicalState, SourceChannel
from app.services import intake as intake_service
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


class TestProcessIntake:
    @pytest.mark.asyncio
    async def test_creates_work_item(self):
        wi = await intake_service.process_intake(message="Build a dashboard")
        assert wi.title == "Build a dashboard"
        assert wi.canonical_state == CanonicalState.TRIAGE  # auto-transitions

    @pytest.mark.asyncio
    async def test_multiline_message_splits_title(self):
        wi = await intake_service.process_intake(
            message="Dashboard request\nWe need a sales dashboard"
        )
        assert wi.title == "Dashboard request"
        assert "sales dashboard" in wi.description

    @pytest.mark.asyncio
    async def test_records_source_channel(self):
        wi = await intake_service.process_intake(
            message="Test", source_channel=SourceChannel.EMAIL
        )
        assert wi.source_channel == SourceChannel.EMAIL

    @pytest.mark.asyncio
    async def test_records_requester(self):
        wi = await intake_service.process_intake(
            message="Test", requester="payas.parab"
        )
        assert wi.requester_person_key == "payas.parab"

    @pytest.mark.asyncio
    async def test_records_external_id(self):
        wi = await intake_service.process_intake(
            message="Test", external_id="ext-123"
        )
        assert wi.source_external_id == "ext-123"

    @pytest.mark.asyncio
    async def test_emits_intake_events(self):
        received = []
        normalized = []

        async def on_received(e): received.append(e)
        async def on_normalized(e): normalized.append(e)

        subscribe("intake.received", on_received)
        subscribe("intake.normalized", on_normalized)

        await intake_service.process_intake(message="Test")
        assert len(received) == 1
        assert len(normalized) == 1

    @pytest.mark.asyncio
    async def test_transitions_to_triage(self):
        wi = await intake_service.process_intake(message="Test")
        assert wi.canonical_state == CanonicalState.TRIAGE

    @pytest.mark.asyncio
    async def test_creates_audit_records(self):
        await intake_service.process_intake(message="Test")
        log = get_audit_log()
        event_names = [r["event_name"] for r in log]
        assert "work_item.created" in event_names
        assert "intake.normalized" in event_names
        assert "work_item.state_changed" in event_names
