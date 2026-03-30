"""Workflow test: BLOCKED and ARCHIVED transitions.

- Any state can transition to BLOCKED and ARCHIVED
- BLOCKED can return to previous state
"""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log
from app.core.events import clear_handlers
from app.domain.enums import CanonicalState
from app.services import work_items
from app.services.work_items import transition_work_item
from app.workflows.engine import WorkflowEngine


@pytest.fixture(autouse=True)
def _clean():
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    work_items.clear_store()
    clear_audit_log()
    clear_handlers()


# All non-terminal states that can go to BLOCKED/ARCHIVED
_BLOCKABLE_STATES = [
    CanonicalState.NEW,
    CanonicalState.TRIAGE,
    CanonicalState.NEEDS_CLARIFICATION,
    CanonicalState.READY_FOR_PRD,
    CanonicalState.PRD_DRAFTING,
    CanonicalState.PRD_REVIEW,
    CanonicalState.APPROVAL_PENDING,
    CanonicalState.APPROVED,
    CanonicalState.READY_FOR_BUILD,
    CanonicalState.IN_PROGRESS,
    CanonicalState.VALIDATION,
    CanonicalState.DEPLOYMENT_PENDING,
    CanonicalState.DEPLOYED,
    CanonicalState.DONE,
    CanonicalState.BLOCKED,
]

# States to advance to before testing BLOCKED/ARCHIVED
_ADVANCE_PATH: dict[CanonicalState, list[CanonicalState]] = {
    CanonicalState.NEW: [],
    CanonicalState.TRIAGE: [CanonicalState.TRIAGE],
    CanonicalState.NEEDS_CLARIFICATION: [CanonicalState.TRIAGE, CanonicalState.NEEDS_CLARIFICATION],
    CanonicalState.READY_FOR_PRD: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD],
    CanonicalState.PRD_DRAFTING: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING],
    CanonicalState.PRD_REVIEW: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW],
    CanonicalState.APPROVAL_PENDING: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING],
    CanonicalState.APPROVED: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED],
    CanonicalState.READY_FOR_BUILD: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD],
    CanonicalState.IN_PROGRESS: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS],
    CanonicalState.VALIDATION: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS, CanonicalState.VALIDATION],
    CanonicalState.DEPLOYMENT_PENDING: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS, CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING],
    CanonicalState.DEPLOYED: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS, CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING, CanonicalState.DEPLOYED],
    CanonicalState.DONE: [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW, CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED, CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS, CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING, CanonicalState.DEPLOYED, CanonicalState.DONE],
    CanonicalState.BLOCKED: [CanonicalState.TRIAGE, CanonicalState.BLOCKED],
}


class TestBlockedTransitions:
    """Test that any non-terminal state can transition to BLOCKED."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target_state", [
        s for s in _BLOCKABLE_STATES if s != CanonicalState.BLOCKED and s != CanonicalState.ARCHIVED
    ])
    async def test_state_can_go_to_blocked(self, target_state: CanonicalState) -> None:
        """Any non-ARCHIVED state can go to BLOCKED."""
        wi = await work_items.create_work_item(title=f"Block from {target_state.value}")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        # Advance to target state
        for state in _ADVANCE_PATH[target_state]:
            await transition_work_item(wi.id, state, actor="test", engine=engine)

        result = await transition_work_item(wi.id, CanonicalState.BLOCKED, actor="test", engine=engine)
        assert result.success, f"Cannot go to BLOCKED from {target_state}: {result.error}"

    @pytest.mark.asyncio
    async def test_blocked_can_return_to_previous_state(self) -> None:
        """BLOCKED can return to any non-terminal state."""
        wi = await work_items.create_work_item(title="Block and unblock")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        # Advance to IN_PROGRESS
        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED,
                      CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS]:
            await transition_work_item(wi.id, state, actor="test", engine=engine)

        # Block
        r = await transition_work_item(wi.id, CanonicalState.BLOCKED, actor="blocker", engine=engine)
        assert r.success

        # Return to IN_PROGRESS
        r = await transition_work_item(wi.id, CanonicalState.IN_PROGRESS, actor="unblocker", engine=engine)
        assert r.success

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.IN_PROGRESS


class TestArchivedTransitions:
    """Test that any non-terminal state can transition to ARCHIVED."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target_state", [
        s for s in _BLOCKABLE_STATES if s != CanonicalState.ARCHIVED
    ])
    async def test_state_can_go_to_archived(self, target_state: CanonicalState) -> None:
        """Any non-ARCHIVED state can go to ARCHIVED."""
        wi = await work_items.create_work_item(title=f"Archive from {target_state.value}")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        # Advance to target state
        for state in _ADVANCE_PATH[target_state]:
            await transition_work_item(wi.id, state, actor="test", engine=engine)

        result = await transition_work_item(wi.id, CanonicalState.ARCHIVED, actor="test", engine=engine)
        assert result.success, f"Cannot go to ARCHIVED from {target_state}: {result.error}"

    @pytest.mark.asyncio
    async def test_archived_is_terminal(self) -> None:
        """ARCHIVED is terminal — no transitions allowed out of it."""
        wi = await work_items.create_work_item(title="Archive terminal")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        await transition_work_item(wi.id, CanonicalState.ARCHIVED, actor="test", engine=engine)

        # Try to transition out
        for target in [CanonicalState.NEW, CanonicalState.TRIAGE, CanonicalState.BLOCKED]:
            result = await transition_work_item(wi.id, target, actor="test", engine=engine)
            assert not result.success, f"Should not be able to leave ARCHIVED to {target}"
