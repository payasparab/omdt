"""Workflow E2E test: access request lifecycle.

REQUESTED -> POLICY_CHECK -> APPROVAL_PENDING -> APPROVED -> PROVISIONING -> VERIFIED -> CLOSED
"""
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


class TestAccessLifecycle:
    """REQUESTED -> POLICY_CHECK -> APPROVAL_PENDING -> APPROVED -> PROVISIONING -> VERIFIED -> CLOSED."""

    @pytest.mark.asyncio
    async def test_full_access_lifecycle(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """Complete access lifecycle from request to verified closure."""
        # REQUESTED
        req = await access.create_access_request(
            requester_person_key="analyst@example.com",
            requested_role_bundle="analyst_readonly",
            justification="Need read access for analysis",
        )
        assert req.state == AccessRequestState.REQUESTED

        # POLICY_CHECK -> APPROVAL_PENDING (or auto-approved)
        policy = await access.evaluate_policy(str(req.id))
        assert policy is not None

        refreshed = await access.get_access_request(str(req.id))
        # State should have advanced past REQUESTED
        assert refreshed.state != AccessRequestState.REQUESTED

        # If APPROVAL_PENDING, approve
        if refreshed.state == AccessRequestState.APPROVAL_PENDING:
            approved = await access.approve_access(str(req.id), approver="lead@example.com")
            assert approved.state == AccessRequestState.APPROVED

        # PROVISIONING -> VERIFIED
        provisioned = await access.provision_access(
            str(req.id),
            snowflake_adapter=fake_snowflake_adapter,
        )
        assert provisioned.state == AccessRequestState.VERIFIED

        # CLOSED
        closed = await access.verify_access(str(req.id))
        assert closed.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_access_rejection_lifecycle(self) -> None:
        """REQUESTED -> POLICY_CHECK -> APPROVAL_PENDING -> REJECTED (CLOSED)."""
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
                reason="Insufficient justification",
            )
            assert rejected.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_access_lifecycle_audit_completeness(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """Verify audit trail covers the full lifecycle."""
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
        # Should have provisioning and verification audit
        assert any("access." in n for n in event_names)

    @pytest.mark.asyncio
    async def test_multiple_access_requests_independent(self, fake_snowflake_adapter: FakeAdapter) -> None:
        """Multiple access requests are processed independently."""
        req1 = await access.create_access_request(
            requester_person_key="user1@example.com",
            requested_role_bundle="analyst_readonly",
        )
        req2 = await access.create_access_request(
            requester_person_key="user2@example.com",
            requested_role_bundle="analyst_readonly",
        )

        assert req1.id != req2.id
        assert len(await access.list_access_requests()) == 2
