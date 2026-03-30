"""End-to-end access request workflow test.

Tests: request -> policy -> approve -> provision -> verify.
"""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import AccessRequestState
from app.services import access as access_service


@pytest.fixture(autouse=True)
def _clean():
    access_service.clear_store()
    access_service.reload_role_bundles()
    clear_audit_log()
    clear_handlers()
    yield
    access_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestAccessFlow:
    @pytest.mark.asyncio
    async def test_end_to_end_with_approval(self):
        """Full lifecycle: request -> policy -> approve -> provision -> verify."""
        provisioned_events = []
        async def on_provisioned(e): provisioned_events.append(e)
        subscribe("access.provisioned", on_provisioned)

        # 1. Create request for a role that needs approval
        request = await access_service.create_access_request(
            requester_person_key="new.user",
            requested_role_bundle="engineer_transform",
            justification="Need access to run transforms",
        )
        assert request.state == AccessRequestState.REQUESTED

        # 2. Evaluate policy
        policy_result = await access_service.evaluate_policy(str(request.id))
        assert policy_result is not None
        assert policy_result.approved is False
        assert policy_result.approval_threshold == "operator"

        request = await access_service.get_access_request(str(request.id))
        assert request.state == AccessRequestState.APPROVAL_PENDING

        # 3. Approve
        request = await access_service.approve_access(str(request.id), "payas.parab")
        assert request.state == AccessRequestState.APPROVED
        assert request.approval_id is not None

        # 4. Provision (without adapter, still transitions state)
        request = await access_service.provision_access(str(request.id))
        assert request.state == AccessRequestState.VERIFIED

        # 5. Verify and close
        request = await access_service.verify_access(str(request.id))
        assert request.state == AccessRequestState.CLOSED

        # Check events
        assert len(provisioned_events) == 1

        # Check audit trail
        log = get_audit_log()
        event_names = [r["event_name"] for r in log]
        assert "access.request_created" in event_names
        assert "access.policy_evaluated" in event_names
        assert "access.approved" in event_names
        assert "access.provisioned" in event_names
        assert "access.verified_and_closed" in event_names

    @pytest.mark.asyncio
    async def test_auto_approved_flow(self):
        """analyst_readonly has approval_threshold: none -> auto-approve."""
        request = await access_service.create_access_request(
            requester_person_key="analyst.user",
            requested_role_bundle="analyst_readonly",
        )
        assert request.state == AccessRequestState.REQUESTED

        # Policy auto-approves
        policy_result = await access_service.evaluate_policy(str(request.id))
        assert policy_result.approved is True

        request = await access_service.get_access_request(str(request.id))
        assert request.state == AccessRequestState.APPROVED

        # Provision directly
        request = await access_service.provision_access(str(request.id))
        assert request.state == AccessRequestState.VERIFIED

    @pytest.mark.asyncio
    async def test_rejected_flow(self):
        """Request -> policy -> reject."""
        request = await access_service.create_access_request(
            requester_person_key="intern",
            requested_role_bundle="admin_breakglass",
        )
        await access_service.evaluate_policy(str(request.id))

        request = await access_service.get_access_request(str(request.id))
        assert request.state == AccessRequestState.APPROVAL_PENDING

        request = await access_service.reject_access(
            str(request.id), "admin", "Not authorized for breakglass"
        )
        assert request.state == AccessRequestState.CLOSED
        assert request.closed_at is not None

    @pytest.mark.asyncio
    async def test_revocation_flow(self):
        """Grant access then revoke it."""
        request = await access_service.create_access_request(
            requester_person_key="leaving.user",
            requested_role_bundle="analyst_readonly",
        )
        await access_service.evaluate_policy(str(request.id))
        await access_service.provision_access(str(request.id))

        # Later: revoke
        revoked = await access_service.revoke_access(
            str(request.id), "Employee offboarding", actor="hr"
        )
        assert revoked.state == AccessRequestState.CLOSED

        log = get_audit_log()
        assert any(r["event_name"] == "access.revoked" for r in log)
