"""Integration test: access request -> policy evaluation -> approval -> provisioning -> verification -> audit trail."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import AccessRequestState
from app.services import access
from tests.conftest import FakeAdapter


@pytest.fixture(autouse=True)
def _clean():
    access.clear_store()
    access.reload_role_bundles()
    clear_audit_log()
    clear_handlers()
    yield
    access.clear_store()
    clear_audit_log()
    clear_handlers()


class TestAccessProvisioning:
    """Access request -> policy evaluation -> approval -> Snowflake provisioning -> verification -> audit trail."""

    @pytest.mark.asyncio
    async def test_full_access_lifecycle(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """End-to-end access provisioning flow."""
        # 1. Create access request
        req = await access.create_access_request(
            requester_person_key="analyst@example.com",
            requested_role_bundle="analyst_readonly",
            justification="Need access for Q1 analysis",
        )
        assert req.state == AccessRequestState.REQUESTED

        # 2. Evaluate policy
        policy_result = await access.evaluate_policy(str(req.id))
        assert policy_result is not None

        # 3. If approval pending, approve
        refreshed = await access.get_access_request(str(req.id))
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            approved = await access.approve_access(str(req.id), approver="lead@example.com")
            assert approved.state == AccessRequestState.APPROVED

        # 4. Provision access
        provisioned = await access.provision_access(
            str(req.id),
            snowflake_adapter=fake_snowflake_adapter,
        )
        assert provisioned is not None
        assert provisioned.state == AccessRequestState.VERIFIED
        fake_snowflake_adapter.assert_called("create_user")
        fake_snowflake_adapter.assert_called("grant_role")

        # 5. Verify and close
        closed = await access.verify_access(str(req.id))
        assert closed.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_access_audit_trail(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """Verify audit events for the access lifecycle."""
        req = await access.create_access_request(
            requester_person_key="user@example.com",
            requested_role_bundle="analyst_readonly",
        )
        await access.evaluate_policy(str(req.id))

        refreshed = await access.get_access_request(str(req.id))
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            await access.approve_access(str(req.id), approver="lead@example.com")

        await access.provision_access(str(req.id), snowflake_adapter=fake_snowflake_adapter)
        await access.verify_access(str(req.id))

        audit = get_audit_log()
        event_names = [r["event_name"] for r in audit]
        assert "access.request_created" in event_names
        assert "access.policy_evaluated" in event_names

    @pytest.mark.asyncio
    async def test_rejected_access_closes_request(self) -> None:
        """Rejected access request transitions to CLOSED."""
        req = await access.create_access_request(
            requester_person_key="user@example.com",
            requested_role_bundle="analyst_readonly",
        )
        await access.evaluate_policy(str(req.id))

        refreshed = await access.get_access_request(str(req.id))
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            rejected = await access.reject_access(
                str(req.id),
                approver="lead@example.com",
                reason="Not justified",
            )
            assert rejected.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_provisioning_failure_reverts_state(self) -> None:
        """If provisioning fails, state reverts to APPROVED for retry."""
        failing_adapter = FakeAdapter()

        async def fail_execute(action, params):
            raise RuntimeError("Snowflake connection failed")

        failing_adapter.execute = fail_execute

        req = await access.create_access_request(
            requester_person_key="user@example.com",
            requested_role_bundle="analyst_readonly",
        )
        await access.evaluate_policy(str(req.id))

        refreshed = await access.get_access_request(str(req.id))
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            await access.approve_access(str(req.id), approver="lead@example.com")

        result = await access.provision_access(str(req.id), snowflake_adapter=failing_adapter)
        assert result.state == AccessRequestState.APPROVED  # reverted for retry

    @pytest.mark.asyncio
    async def test_revoke_access(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """Revoking access closes the request and calls adapter."""
        req = await access.create_access_request(
            requester_person_key="user@example.com",
            requested_role_bundle="analyst_readonly",
        )
        # Shortcut to verified state
        await access.evaluate_policy(str(req.id))
        refreshed = await access.get_access_request(str(req.id))
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            await access.approve_access(str(req.id), approver="lead@example.com")
        await access.provision_access(str(req.id), snowflake_adapter=fake_snowflake_adapter)

        revoked = await access.revoke_access(
            str(req.id),
            reason="Role no longer needed",
            actor="admin@example.com",
            snowflake_adapter=fake_snowflake_adapter,
        )
        assert revoked.state == AccessRequestState.CLOSED
        fake_snowflake_adapter.assert_called("revoke_role")
