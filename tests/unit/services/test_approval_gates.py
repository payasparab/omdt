"""Tests for approval gates — every action requiring approval is enforced."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import ApprovalStatus, CanonicalState
from app.services import approvals, work_items
from app.services.work_items import transition_work_item
from app.workflows.engine import WorkflowEngine
from app.workflows.transitions import requires_approval


@pytest.fixture(autouse=True)
def _clean():
    work_items.clear_store()
    approvals.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    work_items.clear_store()
    approvals.clear_store()
    clear_audit_log()
    clear_handlers()


class TestApprovalGateEnforcement:
    """Test every action that requires approval actually checks for it."""

    @pytest.mark.asyncio
    async def test_approval_pending_to_approved_blocked_without_approval(self) -> None:
        """APPROVAL_PENDING -> APPROVED is blocked without approval checker."""
        wi = await work_items.create_work_item(title="Gate test")
        engine = WorkflowEngine()  # No approval checker

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine)

        result = await transition_work_item(wi.id, CanonicalState.APPROVED, actor="pm", engine=engine)
        assert not result.success
        assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_deployment_pending_to_deployed_blocked_without_approval(self) -> None:
        """DEPLOYMENT_PENDING -> DEPLOYED is blocked without approval checker."""
        wi = await work_items.create_work_item(title="Deploy gate test")
        engine_ok = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)
        engine_none = WorkflowEngine()

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED,
                      CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS,
                      CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine_ok)

        result = await transition_work_item(wi.id, CanonicalState.DEPLOYED, actor="pm", engine=engine_none)
        assert not result.success
        assert result.requires_approval is True


class TestApprovedActionsProceed:
    """Test approved actions proceed through the gate."""

    @pytest.mark.asyncio
    async def test_approved_checker_allows_transition(self) -> None:
        """With approval checker returning True, guarded transition succeeds."""
        wi = await work_items.create_work_item(title="Approved proceed")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED]:
            result = await transition_work_item(wi.id, state, actor="pm", engine=engine)
            assert result.success

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.APPROVED


class TestRejectedActionsBlock:
    """Test rejected actions block the transition."""

    @pytest.mark.asyncio
    async def test_rejected_checker_blocks_transition(self) -> None:
        """With approval checker returning False, guarded transition fails."""
        wi = await work_items.create_work_item(title="Rejected block")
        engine_ok = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)
        engine_reject = WorkflowEngine(approval_checker=lambda wi_id, f, t: False)

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine_ok)

        result = await transition_work_item(wi.id, CanonicalState.APPROVED, actor="pm", engine=engine_reject)
        assert not result.success
        assert result.requires_approval is True


class TestMissingApprovalBlocks:
    """Test missing approval (no checker) blocks transitions."""

    @pytest.mark.asyncio
    async def test_no_approval_checker_blocks(self) -> None:
        """Without an approval checker, guarded transitions always fail."""
        wi = await work_items.create_work_item(title="Missing approval")
        engine = WorkflowEngine()  # No approval checker = None

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine)

        result = await transition_work_item(wi.id, CanonicalState.APPROVED, actor="pm", engine=engine)
        assert not result.success
        assert result.requires_approval is True


class TestApprovalRecordsImmutable:
    """Test that approval records are immutable after decision."""

    @pytest.mark.asyncio
    async def test_approved_request_cannot_be_re_approved(self) -> None:
        """An already-approved request cannot be approved again."""
        ar = await approvals.create_approval_request(
            work_item_id="wi-001",
            action="deploy",
            requester="pm@example.com",
            approvers=["lead@example.com"],
        )
        # First approval
        result = await approvals.approve(ar.id, "lead@example.com", "Looks good")
        assert result.status == ApprovalStatus.APPROVED

        # Second approval attempt — should return same record without changing
        result2 = await approvals.approve(ar.id, "other@example.com", "Also approve")
        assert result2.status == ApprovalStatus.APPROVED
        assert result2.decided_by == "lead@example.com"  # original approver

    @pytest.mark.asyncio
    async def test_rejected_request_cannot_be_approved(self) -> None:
        """A rejected request cannot be subsequently approved."""
        ar = await approvals.create_approval_request(
            work_item_id="wi-002",
            action="deploy",
            requester="pm@example.com",
            approvers=["lead@example.com"],
        )
        await approvals.reject(ar.id, "lead@example.com", "Not ready")

        result = await approvals.approve(ar.id, "lead@example.com", "Changed mind")
        assert result.status == ApprovalStatus.REJECTED  # immutable

    @pytest.mark.asyncio
    async def test_approved_request_cannot_be_rejected(self) -> None:
        """An approved request cannot be subsequently rejected."""
        ar = await approvals.create_approval_request(
            work_item_id="wi-003",
            action="access_grant",
            requester="user@example.com",
            approvers=["admin@example.com"],
        )
        await approvals.approve(ar.id, "admin@example.com", "Approved")

        result = await approvals.reject(ar.id, "admin@example.com", "Wait, no")
        assert result.status == ApprovalStatus.APPROVED  # immutable

    @pytest.mark.asyncio
    async def test_approval_records_audit_trail(self) -> None:
        """Approval actions create audit records."""
        ar = await approvals.create_approval_request(
            work_item_id="wi-004",
            action="production_deploy",
            requester="pm@example.com",
            approvers=["lead@example.com"],
        )
        await approvals.approve(ar.id, "lead@example.com", "Ship it")

        audit = get_audit_log()
        event_names = [r["event_name"] for r in audit]
        assert "approval.requested" in event_names
        assert "approval.approved" in event_names

    def test_transition_rules_mark_correct_gates(self) -> None:
        """Verify the transitions module correctly identifies approval-required transitions."""
        assert requires_approval(CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED) is True
        assert requires_approval(CanonicalState.DEPLOYMENT_PENDING, CanonicalState.DEPLOYED) is True
        # Non-guarded transitions should not require approval
        assert requires_approval(CanonicalState.NEW, CanonicalState.TRIAGE) is False
        assert requires_approval(CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD) is False
