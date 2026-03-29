"""State transition rules for the canonical work-item lifecycle.

Defines ALL allowed transitions per Appendix A of the PRD.
"""
from __future__ import annotations

from app.domain.enums import CanonicalState

S = CanonicalState

# ---------------------------------------------------------------------------
# Explicit forward transitions (the "happy path" plus loops)
# ---------------------------------------------------------------------------

_FORWARD_TRANSITIONS: dict[CanonicalState, set[CanonicalState]] = {
    S.NEW: {S.TRIAGE},
    S.TRIAGE: {S.NEEDS_CLARIFICATION, S.READY_FOR_PRD},
    S.NEEDS_CLARIFICATION: {S.TRIAGE},
    S.READY_FOR_PRD: {S.PRD_DRAFTING},
    S.PRD_DRAFTING: {S.PRD_REVIEW},
    S.PRD_REVIEW: {S.PRD_DRAFTING, S.APPROVAL_PENDING},
    S.APPROVAL_PENDING: {S.APPROVED},
    S.APPROVED: {S.READY_FOR_BUILD},
    S.READY_FOR_BUILD: {S.IN_PROGRESS},
    S.IN_PROGRESS: {S.VALIDATION},
    S.VALIDATION: {S.IN_PROGRESS, S.DEPLOYMENT_PENDING},
    S.DEPLOYMENT_PENDING: {S.DEPLOYED},
    S.DEPLOYED: {S.DONE},
    S.DONE: set(),
    S.BLOCKED: set(),
    S.ARCHIVED: set(),
}

# States that are fully terminal — no outgoing transitions at all.
_TERMINAL_STATES: set[CanonicalState] = {S.ARCHIVED}

# States that cannot go to BLOCKED or ARCHIVED (only ARCHIVED itself is truly
# terminal; DONE can still go to BLOCKED/ARCHIVED).
_NO_UNIVERSAL_OUTGOING: set[CanonicalState] = {S.ARCHIVED}

# Transitions that require human approval before being executed.
_APPROVAL_REQUIRED: set[tuple[CanonicalState, CanonicalState]] = {
    (S.APPROVAL_PENDING, S.APPROVED),
    (S.DEPLOYMENT_PENDING, S.DEPLOYED),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_valid_transition(from_state: CanonicalState, to_state: CanonicalState) -> bool:
    """Return ``True`` if moving from *from_state* to *to_state* is allowed."""
    if from_state in _TERMINAL_STATES:
        return False

    # BLOCKED can return to any non-terminal state (universal return)
    if from_state == S.BLOCKED and to_state not in _TERMINAL_STATES:
        return True

    # Explicit forward transitions
    if to_state in _FORWARD_TRANSITIONS.get(from_state, set()):
        return True

    # Universal: any non-terminal, non-BLOCKED/ARCHIVED, non-DONE state can
    # go to BLOCKED or ARCHIVED.  DONE can also go to BLOCKED/ARCHIVED.
    if to_state in {S.BLOCKED, S.ARCHIVED} and from_state not in _NO_UNIVERSAL_OUTGOING:
        return True

    return False


def get_allowed_transitions(from_state: CanonicalState) -> list[CanonicalState]:
    """Return every state reachable from *from_state* in a single step."""
    if from_state in _TERMINAL_STATES:
        return []

    allowed: set[CanonicalState] = set()

    # BLOCKED: can return to any non-terminal state
    if from_state == S.BLOCKED:
        allowed = {s for s in CanonicalState if s not in _TERMINAL_STATES}
    else:
        # Explicit forward transitions
        allowed = set(_FORWARD_TRANSITIONS.get(from_state, set()))
        # Universal outgoing
        if from_state not in _NO_UNIVERSAL_OUTGOING:
            allowed |= {S.BLOCKED, S.ARCHIVED}

    return sorted(allowed, key=lambda s: list(CanonicalState).index(s))


def requires_approval(from_state: CanonicalState, to_state: CanonicalState) -> bool:
    """Return ``True`` if the transition requires human approval."""
    return (from_state, to_state) in _APPROVAL_REQUIRED
