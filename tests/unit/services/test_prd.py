"""Tests for the PRD service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import PRDStatus
from app.services import prd as prd_service


@pytest.fixture(autouse=True)
def _clean():
    prd_service.clear_stores()
    clear_audit_log()
    clear_handlers()
    yield
    prd_service.clear_stores()
    clear_audit_log()
    clear_handlers()


class TestCreatePRDDraft:
    @pytest.mark.asyncio
    async def test_creates_draft(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft content", author="payas"
        )
        assert prd.status == PRDStatus.DRAFT
        assert prd.revision_number == 1
        assert prd.content == "Draft content"

    @pytest.mark.asyncio
    async def test_increments_revision_number(self):
        await prd_service.create_prd_draft(
            work_item_id="wi-1", content="v1", author="payas"
        )
        prd2 = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="v2", author="payas"
        )
        assert prd2.revision_number == 2

    @pytest.mark.asyncio
    async def test_emits_prd_created_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("prd.created", handler)

        await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        assert len(events) == 1


class TestSubmitForReview:
    @pytest.mark.asyncio
    async def test_submit_changes_status(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        fb = await prd_service.submit_for_review(prd.id)
        assert fb is not None
        assert prd.status == PRDStatus.IN_REVIEW

    @pytest.mark.asyncio
    async def test_submit_frozen_prd_returns_none(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        fb = await prd_service.submit_for_review(prd.id)
        assert fb is None


class TestIncorporateFeedback:
    @pytest.mark.asyncio
    async def test_creates_new_revision(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        new_prd = await prd_service.incorporate_feedback(prd.id, "Fix section 2")
        assert new_prd is not None
        assert new_prd.revision_number == 2
        assert "Fix section 2" in new_prd.content

    @pytest.mark.asyncio
    async def test_feedback_on_frozen_prd_returns_none(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        result = await prd_service.incorporate_feedback(prd.id, "Feedback")
        assert result is None

    @pytest.mark.asyncio
    async def test_emits_prd_revised_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("prd.revised", handler)

        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Draft", author="payas"
        )
        await prd_service.incorporate_feedback(prd.id, "Feedback")
        assert len(events) == 1


class TestApprovePRD:
    @pytest.mark.asyncio
    async def test_approve_freezes_prd(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        approved = await prd_service.approve_prd(prd.id, "approver")
        assert approved.status == PRDStatus.APPROVED
        assert approved.is_frozen is True
        assert approved.frozen_at is not None

    @pytest.mark.asyncio
    async def test_approve_already_frozen_is_idempotent(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        again = await prd_service.approve_prd(prd.id, "approver2")
        assert again.status == PRDStatus.APPROVED

    @pytest.mark.asyncio
    async def test_emits_prd_approved_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("prd.approved", handler)

        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_approve_creates_audit_record(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        log = get_audit_log()
        assert any(r["event_name"] == "prd.approved" for r in log)


class TestPRDImmutability:
    """Approved PRDs must be immutable."""

    @pytest.mark.asyncio
    async def test_cannot_incorporate_feedback_after_approval(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        result = await prd_service.incorporate_feedback(prd.id, "Late feedback")
        assert result is None

    @pytest.mark.asyncio
    async def test_cannot_submit_for_review_after_approval(self):
        prd = await prd_service.create_prd_draft(
            work_item_id="wi-1", content="Final", author="payas"
        )
        await prd_service.approve_prd(prd.id, "approver")
        result = await prd_service.submit_for_review(prd.id)
        assert result is None
