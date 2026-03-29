"""Workflow engine — manages state transitions for work items.

Every transition validates rules, emits domain events, and creates audit records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel

from app.core.audit import record_audit_event
from app.core.events import emit
from app.domain.enums import CanonicalState
from app.domain.models.work_item import WorkItem
from app.workflows.transitions import is_valid_transition, requires_approval


class TransitionResult(BaseModel):
    """Result of a state transition attempt."""

    success: bool
    from_state: CanonicalState
    to_state: CanonicalState
    work_item_id: str = ""
    error: str = ""
    requires_approval: bool = False


# Type for the approval checker callback:
# (work_item_id, from_state, to_state) -> bool
ApprovalChecker = Callable[[str, CanonicalState, CanonicalState], bool]


class WorkflowEngine:
    """Manages state transitions for work items.

    Parameters
    ----------
    approval_checker:
        Optional callback that returns ``True`` if the transition has already
        been approved.  When ``None`` (the default), guarded transitions are
        always rejected — callers must obtain approval first.
    """

    def __init__(
        self,
        approval_checker: ApprovalChecker | None = None,
    ) -> None:
        self._approval_checker = approval_checker

    async def transition(
        self,
        work_item: WorkItem,
        to_state: CanonicalState,
        actor: str,
        reason: str = "",
    ) -> TransitionResult:
        """Attempt to transition *work_item* to *to_state*.

        On success the work item's ``canonical_state`` is mutated in place,
        a domain event is emitted, and an audit record is created.
        """
        from_state = work_item.canonical_state

        # 1. Validate the transition
        if not is_valid_transition(from_state, to_state):
            return TransitionResult(
                success=False,
                from_state=from_state,
                to_state=to_state,
                work_item_id=work_item.id,
                error=f"Invalid transition: {from_state.value} -> {to_state.value}",
            )

        # 2. Check approval requirements
        if requires_approval(from_state, to_state):
            approved = False
            if self._approval_checker is not None:
                approved = self._approval_checker(work_item.id, from_state, to_state)
            if not approved:
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    work_item_id=work_item.id,
                    error="Transition requires approval",
                    requires_approval=True,
                )

        # 3. Apply the transition
        work_item.canonical_state = to_state
        work_item.touch()

        # Set closed_at for terminal-like states
        if to_state in {CanonicalState.DONE, CanonicalState.ARCHIVED}:
            work_item.closed_at = datetime.now(timezone.utc)

        # 4. Emit domain event
        payload = {
            "work_item_id": work_item.id,
            "from_state": from_state.name,
            "to_state": to_state.name,
            "actor": actor,
            "reason": reason,
        }
        await emit("work_item.state_changed", payload)

        # 5. Create audit record
        record_audit_event(
            event_name="work_item.state_changed",
            actor_type="human",
            actor_id=actor,
            object_type="work_item",
            object_id=work_item.id,
            change_summary=f"{from_state.name} -> {to_state.name}: {reason}".rstrip(": "),
        )

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state,
            work_item_id=work_item.id,
        )
