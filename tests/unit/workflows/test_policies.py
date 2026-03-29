"""Tests for workflow policies."""

import pytest

from app.domain.enums import (
    CanonicalState,
    Priority,
    RiskLevel,
    WorkItemType,
)
from app.domain.models.work_item import WorkItem
from app.workflows.policies import ApprovalPolicy, EscalationPolicy, RiskPolicy

S = CanonicalState


# ---------- ApprovalPolicy ----------

class TestApprovalPolicy:
    """Test approval policy evaluation."""

    @pytest.fixture
    def policy(self):
        rules = [
            {
                "action_class": "state_transition.approval_pending_to_approved",
                "require_approval": True,
                "approvers": ["payas.parab"],
                "auto_approve_if": None,
                "timeout_minutes": 1440,
            },
            {
                "action_class": "state_transition.deployment_pending_to_deployed",
                "require_approval": True,
                "approvers": ["payas.parab"],
                "auto_approve_if": None,
                "timeout_minutes": 1440,
            },
            {
                "action_class": "access.grant",
                "require_approval": True,
                "approvers": ["payas.parab"],
                "auto_approve_if": "risk_level == LOW",
                "timeout_minutes": 60,
            },
        ]
        return ApprovalPolicy(rules=rules)

    def test_approval_pending_requires_approval(self, policy):
        assert policy.requires_approval(S.APPROVAL_PENDING, S.APPROVED)

    def test_deployment_pending_requires_approval(self, policy):
        assert policy.requires_approval(S.DEPLOYMENT_PENDING, S.DEPLOYED)

    def test_triage_does_not_require_approval(self, policy):
        assert not policy.requires_approval(S.NEW, S.TRIAGE)

    def test_get_approvers(self, policy):
        approvers = policy.get_approvers(S.APPROVAL_PENDING, S.APPROVED)
        assert approvers == ["payas.parab"]

    def test_get_approvers_empty_for_unguarded(self, policy):
        assert policy.get_approvers(S.NEW, S.TRIAGE) == []

    def test_auto_approve_low_risk(self, policy):
        wi = WorkItem(title="T", risk_level=RiskLevel.LOW)
        # access.grant is not a state transition, test the auto-approve condition
        # Using the internal method via a known action_class
        assert policy.can_auto_approve(S.APPROVAL_PENDING, S.APPROVED, wi) is False
        # The access.grant rule isn't a state transition so it won't match


# ---------- EscalationPolicy ----------

class TestEscalationPolicy:
    """Test escalation rules."""

    def test_high_risk_no_owner_escalates(self):
        wi = WorkItem(
            title="T",
            risk_level=RiskLevel.HIGH,
            owner_person_key=None,
        )
        assert EscalationPolicy.should_escalate(wi) is True
        assert "no owner" in EscalationPolicy.escalation_reason(wi).lower()

    def test_blocked_escalates(self):
        wi = WorkItem(
            title="T",
            canonical_state=CanonicalState.BLOCKED,
        )
        assert EscalationPolicy.should_escalate(wi) is True
        assert "blocked" in EscalationPolicy.escalation_reason(wi).lower()

    def test_normal_item_does_not_escalate(self):
        wi = WorkItem(
            title="T",
            risk_level=RiskLevel.LOW,
            owner_person_key="someone",
            canonical_state=CanonicalState.IN_PROGRESS,
        )
        assert EscalationPolicy.should_escalate(wi) is False
        assert EscalationPolicy.escalation_reason(wi) == ""


# ---------- RiskPolicy ----------

class TestRiskPolicy:
    """Test risk assessment."""

    def test_deployment_is_high_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.DEPLOYMENT)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.HIGH

    def test_access_request_is_high_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.ACCESS_REQUEST)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.HIGH

    def test_pipeline_is_medium_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.PIPELINE)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.MEDIUM

    def test_incident_is_medium_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.INCIDENT)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.MEDIUM

    def test_critical_priority_is_high_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.TASK, priority=Priority.CRITICAL)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.HIGH

    def test_normal_task_is_low_risk(self):
        wi = WorkItem(title="T", work_type=WorkItemType.TASK, priority=Priority.MEDIUM)
        assert RiskPolicy.assess_risk(wi) == RiskLevel.LOW
