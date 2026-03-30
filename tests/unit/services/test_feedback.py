"""Tests for the feedback routing service."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import SourceChannel
from app.services import feedback as fb_service
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    fb_service.clear_stores()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    fb_service.clear_stores()
    clear_audit_log()
    clear_handlers()


class TestChannelSelection:
    def test_reply_defaults_to_source(self):
        ch = fb_service.select_reply_channel(SourceChannel.OUTLOOK)
        assert ch == SourceChannel.OUTLOOK

    def test_fallback_when_source_unavailable(self):
        ch = fb_service.select_reply_channel(
            SourceChannel.NOTION,
            available_channels=[SourceChannel.OUTLOOK, SourceChannel.LINEAR],
        )
        assert ch == SourceChannel.OUTLOOK  # first in fallback order

    def test_none_source_falls_back_to_email(self):
        ch = fb_service.select_reply_channel(None)
        assert ch == SourceChannel.EMAIL


class TestFeedbackRoutingDecision:
    def test_build_routing_decision(self):
        decision = fb_service.build_routing_decision(
            work_item_id="wi-1",
            source_channel=SourceChannel.OUTLOOK,
            participants=["alice", "bob"],
        )
        assert decision.preferred_reply_channel == SourceChannel.OUTLOOK
        assert len(decision.participants) == 2
        assert decision.requires_human_approval is False

    def test_routing_decision_with_approval(self):
        decision = fb_service.build_routing_decision(
            work_item_id="wi-1",
            source_channel=SourceChannel.LINEAR,
            participants=["alice"],
            requires_human_approval=True,
        )
        assert decision.requires_human_approval is True


class TestCreateFeedbackRequest:
    @pytest.mark.asyncio
    async def test_create_request(self):
        wi = await wi_service.create_work_item(title="Feedback test")
        fb = await fb_service.create_feedback_request(
            work_item_id=wi.id,
            participants=["alice", "bob"],
            source_channel=SourceChannel.OUTLOOK,
        )
        assert fb.status == "pending"
        assert fb.requested_from == ["alice", "bob"]

    @pytest.mark.asyncio
    async def test_create_request_emits_event(self):
        events = []
        subscribe("feedback.request_created", lambda e: events.append(e))

        wi = await wi_service.create_work_item(title="Event test")
        await fb_service.create_feedback_request(
            work_item_id=wi.id, participants=["alice"],
        )
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_create_request_writes_audit(self):
        wi = await wi_service.create_work_item(title="Audit test")
        await fb_service.create_feedback_request(
            work_item_id=wi.id, participants=["alice"],
        )
        log = get_audit_log()
        assert any(r["event_name"] == "feedback.request_created" for r in log)


class TestRecordFeedbackResponse:
    @pytest.mark.asyncio
    async def test_record_response(self):
        wi = await wi_service.create_work_item(title="Response test")
        fb = await fb_service.create_feedback_request(
            work_item_id=wi.id, participants=["alice"],
        )
        fb_id = str(fb.id)

        response = await fb_service.record_feedback_response(
            feedback_request_id=fb_id,
            responder="alice",
            content="Looks good!",
            channel=SourceChannel.OUTLOOK,
        )
        assert response.respondent_person_key == "alice"

    @pytest.mark.asyncio
    async def test_auto_resolve_when_all_responded(self):
        wi = await wi_service.create_work_item(title="Auto resolve")
        fb = await fb_service.create_feedback_request(
            work_item_id=wi.id, participants=["alice", "bob"],
        )
        fb_id = str(fb.id)

        await fb_service.record_feedback_response(fb_id, "alice", "LGTM")
        # Not yet resolved
        assert fb.status == "pending"

        await fb_service.record_feedback_response(fb_id, "bob", "LGTM too")
        # Now resolved
        assert fb.status == "resolved"

    @pytest.mark.asyncio
    async def test_response_missing_request(self):
        with pytest.raises(ValueError, match="Feedback request not found"):
            await fb_service.record_feedback_response("nonexistent", "alice", "Hello")


class TestParticipantTracking:
    @pytest.mark.asyncio
    async def test_get_feedback_status(self):
        wi = await wi_service.create_work_item(title="Status test")
        fb = await fb_service.create_feedback_request(
            work_item_id=wi.id,
            prd_id=wi.id,  # using work item id as prd id for test
            participants=["alice", "bob"],
        )
        fb_id = str(fb.id)

        await fb_service.record_feedback_response(fb_id, "alice", "OK")

        status = await fb_service.get_feedback_status(wi.id)
        assert status["total_requests"] == 1
        assert status["pending"] == 1
        req = status["requests"][0]
        assert "alice" in req["responded_by"]
        assert "bob" in req["pending_from"]

    @pytest.mark.asyncio
    async def test_status_empty(self):
        status = await fb_service.get_feedback_status("nonexistent-prd")
        assert status["total_requests"] == 0
