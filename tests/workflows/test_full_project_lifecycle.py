"""Workflow E2E test: full standard project lifecycle from NEW to DONE (Appendix A)."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
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


# Full happy-path sequence from Appendix A
STANDARD_LIFECYCLE = [
    CanonicalState.TRIAGE,
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
]


class TestFullProjectLifecycle:
    """Test the ENTIRE Standard Project Lifecycle from Appendix A."""

    @pytest.mark.asyncio
    async def test_complete_happy_path(self) -> None:
        """NEW -> TRIAGE -> ... -> DONE with approval checker."""
        wi = await work_items.create_work_item(title="Full lifecycle test")
        assert wi.canonical_state == CanonicalState.NEW

        # Approval checker that always approves
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for target_state in STANDARD_LIFECYCLE:
            result = await transition_work_item(
                wi.id, target_state, actor="test_actor", engine=engine,
            )
            assert result.success, f"Failed transition to {target_state}: {result.error}"

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.DONE
        assert refreshed.closed_at is not None

    @pytest.mark.asyncio
    async def test_each_transition_emits_event(self) -> None:
        """Each state transition emits a work_item.state_changed event."""
        state_events: list[dict] = []
        subscribe("work_item.state_changed", lambda p: state_events.append(p))

        wi = await work_items.create_work_item(title="Events test")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for target_state in STANDARD_LIFECYCLE:
            await transition_work_item(wi.id, target_state, actor="test", engine=engine)

        assert len(state_events) == len(STANDARD_LIFECYCLE)

        # Verify transitions are in order
        for i, evt in enumerate(state_events):
            assert evt["to_state"] == STANDARD_LIFECYCLE[i].name

    @pytest.mark.asyncio
    async def test_each_transition_creates_audit_record(self) -> None:
        """Each state transition creates an audit record."""
        wi = await work_items.create_work_item(title="Audit test")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for target_state in STANDARD_LIFECYCLE:
            await transition_work_item(wi.id, target_state, actor="test", engine=engine)

        audit = get_audit_log()
        state_changes = [r for r in audit if r["event_name"] == "work_item.state_changed"]
        assert len(state_changes) == len(STANDARD_LIFECYCLE)

    @pytest.mark.asyncio
    async def test_clarification_loop(self) -> None:
        """TRIAGE -> NEEDS_CLARIFICATION -> TRIAGE -> READY_FOR_PRD."""
        wi = await work_items.create_work_item(title="Clarification loop")

        r1 = await transition_work_item(wi.id, CanonicalState.TRIAGE, actor="system")
        assert r1.success

        r2 = await transition_work_item(wi.id, CanonicalState.NEEDS_CLARIFICATION, actor="triage")
        assert r2.success

        r3 = await transition_work_item(wi.id, CanonicalState.TRIAGE, actor="requester")
        assert r3.success

        r4 = await transition_work_item(wi.id, CanonicalState.READY_FOR_PRD, actor="triage")
        assert r4.success

    @pytest.mark.asyncio
    async def test_prd_review_loop(self) -> None:
        """PRD_REVIEW -> PRD_DRAFTING -> PRD_REVIEW (revision loop)."""
        wi = await work_items.create_work_item(title="PRD review loop")
        engine = WorkflowEngine()

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD, CanonicalState.PRD_DRAFTING]:
            await transition_work_item(wi.id, state, actor="pm", engine=engine)

        # Enter review
        await transition_work_item(wi.id, CanonicalState.PRD_REVIEW, actor="pm", engine=engine)
        # Send back for revision
        await transition_work_item(wi.id, CanonicalState.PRD_DRAFTING, actor="reviewer", engine=engine)
        # Re-submit for review
        await transition_work_item(wi.id, CanonicalState.PRD_REVIEW, actor="pm", engine=engine)

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.PRD_REVIEW

    @pytest.mark.asyncio
    async def test_validation_loop(self) -> None:
        """VALIDATION -> IN_PROGRESS -> VALIDATION (fix-and-retry loop)."""
        wi = await work_items.create_work_item(title="Validation loop")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        # Advance to VALIDATION
        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW,
                      CanonicalState.APPROVAL_PENDING, CanonicalState.APPROVED,
                      CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS,
                      CanonicalState.VALIDATION]:
            await transition_work_item(wi.id, state, actor="test", engine=engine)

        # Send back to IN_PROGRESS for fixes
        await transition_work_item(wi.id, CanonicalState.IN_PROGRESS, actor="qa", engine=engine)
        # Re-validate
        await transition_work_item(wi.id, CanonicalState.VALIDATION, actor="dev", engine=engine)

        refreshed = await work_items.get_work_item(wi.id)
        assert refreshed.canonical_state == CanonicalState.VALIDATION
