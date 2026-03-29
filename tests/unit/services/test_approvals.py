"""Tests for the approval service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import ApprovalStatus
from app.services import approvals as approval_service


@pytest.fixture(autouse=True)
def _clean():
    approval_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    approval_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestCreateApprovalRequest:
    @pytest.mark.asyncio
    async def test_creates_pending_request(self):
        ar = await approval_service.create_approval_request(
            work_item_id="wi-1",
            action="deploy",
            requester="user1",
            approvers=["payas.parab"],
        )
        assert ar.status == ApprovalStatus.PENDING
        assert ar.approvers == ["payas.parab"]

    @pytest.mark.asyncio
    async def test_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("approval.requested", handler)

        await approval_service.create_approval_request(
            work_item_id="wi-1",
            action="deploy",
            requester="user1",
            approvers=["payas.parab"],
        )
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_creates_audit_record(self):
        await approval_service.create_approval_request(
            work_item_id="wi-1",
            action="deploy",
            requester="user1",
            approvers=["payas.parab"],
        )
        assert any(r["event_name"] == "approval.requested" for r in get_audit_log())


class TestApprove:
    @pytest.mark.asyncio
    async def test_approve_changes_status(self):
        ar = await approval_service.create_approval_request(
            work_item_id="wi-1",
            action="deploy",
            requester="user1",
            approvers=["payas.parab"],
        )
        result = await approval_service.approve(ar.id, "payas.parab", "LGTM")
        assert result.status == ApprovalStatus.APPROVED
        assert result.decided_by == "payas.parab"
        assert result.decided_at is not None

    @pytest.mark.asyncio
    async def test_approve_already_decided_no_change(self):
        ar = await approval_service.create_approval_request(
            work_item_id="wi-1",
            action="deploy",
            requester="user1",
            approvers=["payas.parab"],
        )
        await approval_service.approve(ar.id, "payas.parab")
        result = await approval_service.approve(ar.id, "someone_else")
        assert result.decided_by == "payas.parab"  # original decision stands

    @pytest.mark.asyncio
    async def test_approve_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("approval.approved", handler)

        ar = await approval_service.create_approval_request(
            work_item_id="wi-1", action="deploy", requester="user1",
            approvers=["payas.parab"],
        )
        await approval_service.approve(ar.id, "payas.parab")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_approve_missing_returns_none(self):
        result = await approval_service.approve("nope", "user1")
        assert result is None


class TestReject:
    @pytest.mark.asyncio
    async def test_reject_changes_status(self):
        ar = await approval_service.create_approval_request(
            work_item_id="wi-1", action="deploy", requester="user1",
            approvers=["payas.parab"],
        )
        result = await approval_service.reject(ar.id, "payas.parab", "Not ready")
        assert result.status == ApprovalStatus.REJECTED
        assert result.decision_reason == "Not ready"

    @pytest.mark.asyncio
    async def test_reject_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("approval.rejected", handler)

        ar = await approval_service.create_approval_request(
            work_item_id="wi-1", action="deploy", requester="user1",
            approvers=["payas.parab"],
        )
        await approval_service.reject(ar.id, "payas.parab")
        assert len(events) == 1


class TestGetPendingApprovals:
    @pytest.mark.asyncio
    async def test_returns_pending_only(self):
        ar1 = await approval_service.create_approval_request(
            work_item_id="wi-1", action="a", requester="u", approvers=["p"],
        )
        ar2 = await approval_service.create_approval_request(
            work_item_id="wi-2", action="b", requester="u", approvers=["p"],
        )
        await approval_service.approve(ar1.id, "p")
        pending = await approval_service.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].id == ar2.id

    @pytest.mark.asyncio
    async def test_filter_by_approver(self):
        await approval_service.create_approval_request(
            work_item_id="wi-1", action="a", requester="u", approvers=["alice"],
        )
        await approval_service.create_approval_request(
            work_item_id="wi-2", action="b", requester="u", approvers=["bob"],
        )
        alice_pending = await approval_service.get_pending_approvals("alice")
        assert len(alice_pending) == 1
