"""Workflow test: invalid transitions are rejected and guarded transitions require approval."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log
from app.core.events import clear_handlers
from app.domain.enums import CanonicalState
from app.services import work_items
from app.services.work_items import transition_work_item
from app.workflows.engine import WorkflowEngine
from app.workflows.transitions import is_valid_transition


@pytest.fixture(autouse=True)
def _clean():
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()


# Known invalid transitions (skipping states, going backwards improperly)
INVALID_TRANSITIONS = [
    (CanonicalState.NEW, CanonicalState.DEPLOYED),
    (CanonicalState.NEW, CanonicalState.DONE),
    (CanonicalState.NEW, CanonicalState.IN_PROGRESS),
    (CanonicalState.NEW, CanonicalState.PRD_DRAFTING),
    (CanonicalState.TRIAGE, CanonicalState.DEPLOYED),
    (CanonicalState.TRIAGE, CanonicalState.DONE),
    (CanonicalState.TRIAGE, CanonicalState.APPROVED),
    (CanonicalState.PRD_DRAFTING, CanonicalState.DEPLOYED),
    (CanonicalState.PRD_REVIEW, CanonicalState.DEPLOYED),
    (CanonicalState.IN_PROGRESS, CanonicalState.NEW),
    (CanonicalState.DONE, CanonicalState.NEW),
    (CanonicalState.DEPLOYED, CanonicalState.NEW),
    (CanonicalState.APPROVAL_PENDING, CanonicalState.DEPLOYED),
    (CanonicalState.READY_FOR_BUILD, CanonicalState.NEW),
]


class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""

    @pytest.mark.parametrize("from_state,to_state", INVALID_TRANSITIONS)
    def test_invalid_transition_is_rejected(self, from_state: CanonicalState, to_state: CanonicalState) -> None:
        """Verify transition rules reject invalid state changes."""
        assert not is_valid_transition(from_state, to_state), (
            f"Transition {from_state} -> {to_state} should be invalid"
        )

    @pytest.mark.asyncio
    async def test_invalid_transition_via_engine(self) -> None:
        """WorkflowEngine rejects invalid transitions."""
        wi = await work_items.create_work_item(title="Invalid transition test")
        engine = WorkflowEngine()

        # NEW -> DEPLOYED is invalid
        result = await transition_work_item(
            wi.id, CanonicalState.DEPLOYED, actor="test", engine=engine,
        )
        assert not result.success
        assert "Invalid transition" in result.error

    @pytest.mark.asyncio
    async def test_state_unchanged_after_invalid_transition(self) -> None:
        """Work item state remains unchanged after a rejected transition."""
        wi = await work_items.create_work_item(title="State preservation test")
        assert wi.canonical_state == CanonicalState.NEW

        engine = WorkflowEngine()
        await transition_work_item(wi.id, CanonicalState.DONE, actor="test", engine=engine)

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.NEW


class TestGuardedTransitions:
    """Test that guarded transitions require approval."""

    @pytest.mark.asyncio
    async def test_approval_pending_to_approved_requires_approval(self) -> None:
        """APPROVAL_PENDING -> APPROVED requires approval (no checker = rejected)."""
        wi = await work_items.create_work_item(title="Approval required")
        engine_no_approval = WorkflowEngine()  # No approval checker

        # Advance to APPROVAL_PENDING
        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine_no_approval)

        # Try to go APPROVED without approval checker
        result = await transition_work_item(
            wi.id, CanonicalState.APPROVED, actor="pm", engine=engine_no_approval,
        )
        assert not result.success
        assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_deployment_pending_to_deployed_requires_approval(self) -> None:
        """DEPLOYMENT_PENDING -> DEPLOYED requires approval."""
        wi = await work_items.create_work_item(title="Deploy approval required")
        engine_approve = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)
        engine_no_approve = WorkflowEngine()  # No approval checker

        # Advance to DEPLOYMENT_PENDING
        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED,
                      CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS,
                      CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine_approve)

        # Try DEPLOYED without approval checker
        result = await transition_work_item(
            wi.id, CanonicalState.DEPLOYED, actor="pm", engine=engine_no_approve,
        )
        assert not result.success
        assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_approved_transition_with_checker(self) -> None:
        """Guarded transition succeeds with approval checker returning True."""
        wi = await work_items.create_work_item(title="Approved with checker")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED]:
            result = await transition_work_item(wi.id, state, actor="pm", engine=engine)
            assert result.success, f"Failed at {state}: {result.error}"

    @pytest.mark.asyncio
    async def test_rejected_approval_blocks_transition(self) -> None:
        """Guarded transition fails when approval checker returns False."""
        wi = await work_items.create_work_item(title="Rejected approval")
        engine_approve = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)
        engine_reject = WorkflowEngine(approval_checker=lambda wi_id, f, t: False)

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine_approve)

        result = await transition_work_item(
            wi.id, CanonicalState.APPROVED, actor="pm", engine=engine_reject,
        )
        assert not result.success
        assert result.requires_approval is True
