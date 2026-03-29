"""Tests for the WorkflowEngine."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, emit, subscribe
from app.domain.enums import CanonicalState
from app.domain.models.work_item import WorkItem
from app.workflows.engine import TransitionResult, WorkflowEngine


@pytest.fixture(autouse=True)
def _clean():
    """Clean up audit and event state before each test."""
    clear_audit_log()
    clear_handlers()
    yield
    clear_audit_log()
    clear_handlers()


@pytest.fixture
def engine():
    return WorkflowEngine()


@pytest.fixture
def work_item():
    return WorkItem(title="Test item", canonical_state=CanonicalState.NEW)


class TestWorkflowEngineTransition:
    """Test basic transition behavior."""

    @pytest.mark.asyncio
    async def test_valid_transition_succeeds(self, engine, work_item):
        result = await engine.transition(work_item, CanonicalState.TRIAGE, "user1")
        assert result.success is True
        assert result.from_state == CanonicalState.NEW
        assert result.to_state == CanonicalState.TRIAGE
        assert work_item.canonical_state == CanonicalState.TRIAGE

    @pytest.mark.asyncio
    async def test_invalid_transition_fails(self, engine, work_item):
        result = await engine.transition(work_item, CanonicalState.DEPLOYED, "user1")
        assert result.success is False
        assert "Invalid transition" in result.error
        assert work_item.canonical_state == CanonicalState.NEW  # unchanged

    @pytest.mark.asyncio
    async def test_transition_to_done_sets_closed_at(self, engine):
        wi = WorkItem(title="T", canonical_state=CanonicalState.DEPLOYED)
        result = await engine.transition(wi, CanonicalState.DONE, "user1")
        assert result.success is True
        assert wi.closed_at is not None

    @pytest.mark.asyncio
    async def test_transition_to_archived_sets_closed_at(self, engine):
        wi = WorkItem(title="T", canonical_state=CanonicalState.NEW)
        result = await engine.transition(wi, CanonicalState.ARCHIVED, "user1")
        assert result.success is True
        assert wi.closed_at is not None


class TestWorkflowEngineApproval:
    """Test approval-guarded transitions."""

    @pytest.mark.asyncio
    async def test_guarded_transition_rejected_without_approval(self, engine):
        wi = WorkItem(title="T", canonical_state=CanonicalState.APPROVAL_PENDING)
        result = await engine.transition(wi, CanonicalState.APPROVED, "user1")
        assert result.success is False
        assert result.requires_approval is True
        assert wi.canonical_state == CanonicalState.APPROVAL_PENDING

    @pytest.mark.asyncio
    async def test_guarded_transition_succeeds_with_approval(self):
        def checker(wi_id, from_s, to_s):
            return True

        engine = WorkflowEngine(approval_checker=checker)
        wi = WorkItem(title="T", canonical_state=CanonicalState.APPROVAL_PENDING)
        result = await engine.transition(wi, CanonicalState.APPROVED, "user1")
        assert result.success is True
        assert wi.canonical_state == CanonicalState.APPROVED


class TestWorkflowEngineEvents:
    """Test that transitions emit domain events."""

    @pytest.mark.asyncio
    async def test_transition_emits_event(self, engine, work_item):
        events_received = []

        async def handler(event):
            events_received.append(event)

        subscribe("work_item.state_changed", handler)

        await engine.transition(work_item, CanonicalState.TRIAGE, "user1")
        assert len(events_received) == 1
        assert events_received[0]["from_state"] == "NEW"
        assert events_received[0]["to_state"] == "TRIAGE"

    @pytest.mark.asyncio
    async def test_failed_transition_does_not_emit(self, engine, work_item):
        events_received = []

        async def handler(event):
            events_received.append(event)

        subscribe("work_item.state_changed", handler)

        await engine.transition(work_item, CanonicalState.DEPLOYED, "user1")
        assert len(events_received) == 0


class TestWorkflowEngineAudit:
    """Test that transitions create audit records."""

    @pytest.mark.asyncio
    async def test_transition_creates_audit_record(self, engine, work_item):
        await engine.transition(work_item, CanonicalState.TRIAGE, "user1", "test reason")
        log = get_audit_log()
        assert len(log) == 1
        assert log[0]["event_name"] == "work_item.state_changed"
        assert log[0]["actor_id"] == "user1"
        assert "NEW -> TRIAGE" in log[0]["change_summary"]

    @pytest.mark.asyncio
    async def test_failed_transition_no_audit(self, engine, work_item):
        await engine.transition(work_item, CanonicalState.DEPLOYED, "user1")
        assert len(get_audit_log()) == 0
