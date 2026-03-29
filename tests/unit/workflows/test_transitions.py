"""Tests for state transition rules."""

import pytest

from app.domain.enums import CanonicalState
from app.workflows.transitions import (
    get_allowed_transitions,
    is_valid_transition,
    requires_approval,
)

S = CanonicalState


# ---------- Standard lifecycle forward transitions ----------

class TestStandardLifecycle:
    """Test the happy-path lifecycle: NEW -> ... -> DONE."""

    LIFECYCLE = [
        S.NEW, S.TRIAGE, S.READY_FOR_PRD, S.PRD_DRAFTING, S.PRD_REVIEW,
        S.APPROVAL_PENDING, S.APPROVED, S.READY_FOR_BUILD, S.IN_PROGRESS,
        S.VALIDATION, S.DEPLOYMENT_PENDING, S.DEPLOYED, S.DONE,
    ]

    def test_full_lifecycle_forward(self):
        for i in range(len(self.LIFECYCLE) - 1):
            from_s, to_s = self.LIFECYCLE[i], self.LIFECYCLE[i + 1]
            assert is_valid_transition(from_s, to_s), (
                f"{from_s.value} -> {to_s.value} should be valid"
            )


class TestClarificationLoop:
    """TRIAGE <-> NEEDS_CLARIFICATION loop."""

    def test_triage_to_needs_clarification(self):
        assert is_valid_transition(S.TRIAGE, S.NEEDS_CLARIFICATION)

    def test_needs_clarification_back_to_triage(self):
        assert is_valid_transition(S.NEEDS_CLARIFICATION, S.TRIAGE)


class TestPRDFeedbackLoop:
    """PRD_REVIEW can go back to PRD_DRAFTING."""

    def test_prd_review_to_prd_drafting(self):
        assert is_valid_transition(S.PRD_REVIEW, S.PRD_DRAFTING)


class TestValidationLoop:
    """VALIDATION can go back to IN_PROGRESS."""

    def test_validation_to_in_progress(self):
        assert is_valid_transition(S.VALIDATION, S.IN_PROGRESS)


# ---------- BLOCKED and ARCHIVED universal transitions ----------

class TestBlockedAndArchived:
    """Any non-terminal state can go to BLOCKED or ARCHIVED."""

    NON_TERMINAL = [
        s for s in CanonicalState if s not in {S.ARCHIVED}
    ]

    @pytest.mark.parametrize("from_state", [
        s for s in CanonicalState
        if s not in {S.BLOCKED, S.ARCHIVED, S.DONE}
    ])
    def test_any_state_can_go_to_blocked(self, from_state):
        assert is_valid_transition(from_state, S.BLOCKED)

    @pytest.mark.parametrize("from_state", [
        s for s in CanonicalState
        if s not in {S.BLOCKED, S.ARCHIVED, S.DONE}
    ])
    def test_any_state_can_go_to_archived(self, from_state):
        assert is_valid_transition(from_state, S.ARCHIVED)

    @pytest.mark.parametrize("to_state", [
        s for s in CanonicalState if s not in {S.BLOCKED, S.ARCHIVED}
    ])
    def test_blocked_can_return_to_any(self, to_state):
        assert is_valid_transition(S.BLOCKED, to_state)


# ---------- Invalid transitions ----------

class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""

    def test_cannot_skip_triage(self):
        assert not is_valid_transition(S.NEW, S.PRD_DRAFTING)

    def test_cannot_go_backwards_arbitrarily(self):
        assert not is_valid_transition(S.APPROVED, S.TRIAGE)

    def test_done_is_terminal_for_forward(self):
        # DONE has no forward transitions (only BLOCKED/ARCHIVED via universal)
        allowed = get_allowed_transitions(S.DONE)
        assert S.BLOCKED in allowed
        assert S.ARCHIVED in allowed
        assert S.NEW not in allowed

    def test_archived_is_fully_terminal(self):
        assert get_allowed_transitions(S.ARCHIVED) == []

    def test_new_cannot_go_to_deployed(self):
        assert not is_valid_transition(S.NEW, S.DEPLOYED)


# ---------- Approval requirements ----------

class TestApprovalRequirements:
    """Test which transitions require approval."""

    def test_approval_pending_to_approved_requires_approval(self):
        assert requires_approval(S.APPROVAL_PENDING, S.APPROVED)

    def test_deployment_pending_to_deployed_requires_approval(self):
        assert requires_approval(S.DEPLOYMENT_PENDING, S.DEPLOYED)

    def test_triage_to_ready_does_not_require_approval(self):
        assert not requires_approval(S.TRIAGE, S.READY_FOR_PRD)

    def test_new_to_triage_does_not_require_approval(self):
        assert not requires_approval(S.NEW, S.TRIAGE)


# ---------- get_allowed_transitions ----------

class TestGetAllowedTransitions:
    """Test the get_allowed_transitions function."""

    def test_new_allows_triage_blocked_archived(self):
        allowed = get_allowed_transitions(S.NEW)
        assert S.TRIAGE in allowed
        assert S.BLOCKED in allowed
        assert S.ARCHIVED in allowed

    def test_triage_allows_clarification_and_ready(self):
        allowed = get_allowed_transitions(S.TRIAGE)
        assert S.NEEDS_CLARIFICATION in allowed
        assert S.READY_FOR_PRD in allowed

    def test_archived_has_no_transitions(self):
        assert get_allowed_transitions(S.ARCHIVED) == []
