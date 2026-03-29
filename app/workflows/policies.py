"""Workflow policies — approval, escalation, and risk assessment.

Policies are evaluated during state transitions and work-item processing
to determine when human intervention is required.
"""
from __future__ import annotations

from typing import Any

from app.domain.enums import CanonicalState, Priority, RiskLevel, WorkItemType
from app.domain.models.work_item import WorkItem
from app.workflows.transitions import requires_approval as transition_requires_approval


# ---------------------------------------------------------------------------
# ApprovalPolicy
# ---------------------------------------------------------------------------

class ApprovalPolicy:
    """Evaluate whether a state transition requires human approval.

    Constructed with a list of rule dicts loaded from config/approvals.yaml
    or provided directly in tests.
    """

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules or []

    def _find_rule(
        self, from_state: CanonicalState, to_state: CanonicalState,
    ) -> dict[str, Any] | None:
        action_key = f"state_transition.{from_state.value}_to_{to_state.value}"
        for rule in self._rules:
            if rule.get("action_class") == action_key:
                return rule
        return None

    def requires_approval(
        self, from_state: CanonicalState, to_state: CanonicalState,
    ) -> bool:
        """Return ``True`` if the transition requires human approval."""
        rule = self._find_rule(from_state, to_state)
        if rule is not None:
            return rule.get("require_approval", True)
        # Fall back to the static transition rules
        return transition_requires_approval(from_state, to_state)

    def get_approvers(
        self, from_state: CanonicalState, to_state: CanonicalState,
    ) -> list[str]:
        """Return the list of allowed approvers for a guarded transition."""
        rule = self._find_rule(from_state, to_state)
        if rule is not None:
            return list(rule.get("approvers", []))
        return []

    def can_auto_approve(
        self,
        from_state: CanonicalState,
        to_state: CanonicalState,
        work_item: WorkItem,
    ) -> bool:
        """Return ``True`` if the transition can be auto-approved."""
        rule = self._find_rule(from_state, to_state)
        if rule is None:
            return False
        condition = rule.get("auto_approve_if")
        if condition is None:
            return False
        # Simple condition evaluation
        if "risk_level == LOW" in condition:
            return work_item.risk_level == RiskLevel.LOW
        return False


# ---------------------------------------------------------------------------
# EscalationPolicy
# ---------------------------------------------------------------------------

class EscalationPolicy:
    """Determine when to escalate a work item to the Head of Data."""

    @staticmethod
    def should_escalate(work_item: WorkItem) -> bool:
        """Return ``True`` if the work item should be escalated."""
        # High risk without an owner
        risk = work_item.risk_level
        if risk in {RiskLevel.HIGH, RiskLevel.HIGH.value, "high"} and not work_item.owner_person_key:
            return True
        # BLOCKED items always escalate
        if work_item.canonical_state == CanonicalState.BLOCKED:
            return True
        # Critical priority without owner
        if work_item.priority == Priority.CRITICAL and not work_item.owner_person_key:
            return True
        return False

    @staticmethod
    def escalation_reason(work_item: WorkItem) -> str:
        """Return a human-readable reason for escalation, or empty string."""
        reasons: list[str] = []
        risk = work_item.risk_level
        if risk in {RiskLevel.HIGH, RiskLevel.HIGH.value, "high"} and not work_item.owner_person_key:
            reasons.append("High risk work item with no owner assigned")
        if work_item.canonical_state == CanonicalState.BLOCKED:
            reasons.append("Work item is blocked")
        if work_item.priority == Priority.CRITICAL and not work_item.owner_person_key:
            reasons.append("Critical priority with no owner")
        return "; ".join(reasons)


# ---------------------------------------------------------------------------
# RiskPolicy
# ---------------------------------------------------------------------------

# Work item types that are inherently high-risk
_HIGH_RISK_TYPES: set[WorkItemType] = {
    WorkItemType.DEPLOYMENT,
    WorkItemType.ACCESS_REQUEST,
    WorkItemType.VENDOR_OR_PROCUREMENT,
}

# Work item types that are medium-risk
_MEDIUM_RISK_TYPES: set[WorkItemType] = {
    WorkItemType.PIPELINE,
    WorkItemType.PIPELINE_REQUEST,
    WorkItemType.BUG_OR_INCIDENT,
    WorkItemType.INCIDENT,
}


class RiskPolicy:
    """Assess risk level of work items based on type and priority."""

    @staticmethod
    def assess_risk(work_item: WorkItem) -> RiskLevel:
        """Return the assessed risk level for a work item."""
        # Critical priority always means high risk
        if work_item.priority == Priority.CRITICAL:
            return RiskLevel.HIGH

        # Type-based risk
        if work_item.work_type in _HIGH_RISK_TYPES:
            return RiskLevel.HIGH
        if work_item.work_type in _MEDIUM_RISK_TYPES:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW
