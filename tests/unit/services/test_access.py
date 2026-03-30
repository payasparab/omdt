"""Tests for the access request service."""

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


class TestCreateAccessRequest:
    @pytest.mark.asyncio
    async def test_create_returns_request(self):
        r = await access_service.create_access_request(
            requester_person_key="payas.parab",
            requested_role_bundle="analyst_readonly",
            justification="Need to run reports",
        )
        assert r.requester_person_key == "payas.parab"
        assert r.requested_role_bundle == "analyst_readonly"
        assert r.state == AccessRequestState.REQUESTED

    @pytest.mark.asyncio
    async def test_create_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("access.request_created", handler)

        await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        assert len(events) == 1
        assert events[0]["requester"] == "user1"

    @pytest.mark.asyncio
    async def test_create_writes_audit(self):
        await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        log = get_audit_log()
        assert any(r["event_name"] == "access.request_created" for r in log)


class TestEvaluatePolicy:
    @pytest.mark.asyncio
    async def test_auto_approve_no_threshold(self):
        """analyst_readonly has approval_threshold: none -> auto-approve."""
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        result = await access_service.evaluate_policy(str(r.id))
        assert result is not None
        assert result.approved is True
        assert result.approval_threshold == "none"

        # State should now be APPROVED
        req = await access_service.get_access_request(str(r.id))
        assert req.state == AccessRequestState.APPROVED

    @pytest.mark.asyncio
    async def test_requires_approval(self):
        """engineer_transform has approval_threshold: operator -> needs approval."""
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        result = await access_service.evaluate_policy(str(r.id))
        assert result is not None
        assert result.approved is False
        assert result.approval_threshold == "operator"

        req = await access_service.get_access_request(str(r.id))
        assert req.state == AccessRequestState.APPROVAL_PENDING

    @pytest.mark.asyncio
    async def test_unknown_role_bundle(self):
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="nonexistent_bundle",
        )
        result = await access_service.evaluate_policy(str(r.id))
        assert result is not None
        assert result.approved is False
        assert "Unknown" in result.reason

    @pytest.mark.asyncio
    async def test_evaluate_missing_request(self):
        result = await access_service.evaluate_policy("nonexistent")
        assert result is None


class TestApproveAccess:
    @pytest.mark.asyncio
    async def test_approve(self):
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        await access_service.evaluate_policy(str(r.id))
        approved = await access_service.approve_access(str(r.id), "admin")
        assert approved.state == AccessRequestState.APPROVED
        assert approved.approval_id is not None

    @pytest.mark.asyncio
    async def test_approve_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("access.approved", handler)

        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.approve_access(str(r.id), "admin")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_approve_writes_audit(self):
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.approve_access(str(r.id), "admin")
        log = get_audit_log()
        assert any(r["event_name"] == "access.approved" for r in log)


class TestRejectAccess:
    @pytest.mark.asyncio
    async def test_reject(self):
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        await access_service.evaluate_policy(str(r.id))
        rejected = await access_service.reject_access(str(r.id), "admin", "Not authorized")
        assert rejected.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_reject_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("access.rejected", handler)

        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.reject_access(str(r.id), "admin", "denied")
        assert len(events) == 1


class TestProvisionAccess:
    @pytest.mark.asyncio
    async def test_provision_without_adapter(self):
        """Provisioning without Snowflake adapter still updates state."""
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        await access_service.evaluate_policy(str(r.id))
        # analyst_readonly auto-approves

        provisioned = await access_service.provision_access(str(r.id))
        assert provisioned.state == AccessRequestState.VERIFIED

    @pytest.mark.asyncio
    async def test_provision_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("access.provisioned", handler)

        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.provision_access(str(r.id))
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_provision_not_approved_noop(self):
        """Can't provision if not in APPROVED state."""
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="engineer_transform",
        )
        # Not yet evaluated / approved
        result = await access_service.provision_access(str(r.id))
        assert result.state == AccessRequestState.REQUESTED


class TestRevokeAccess:
    @pytest.mark.asyncio
    async def test_revoke(self):
        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.provision_access(str(r.id))

        revoked = await access_service.revoke_access(str(r.id), "Employee offboarding")
        assert revoked.state == AccessRequestState.CLOSED

    @pytest.mark.asyncio
    async def test_revoke_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("access.revoked", handler)

        r = await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        await access_service.evaluate_policy(str(r.id))
        await access_service.provision_access(str(r.id))
        await access_service.revoke_access(str(r.id), "offboarding")
        assert len(events) == 1


class TestListAccessRequests:
    @pytest.mark.asyncio
    async def test_list_all(self):
        await access_service.create_access_request(
            requester_person_key="a", requested_role_bundle="analyst_readonly",
        )
        await access_service.create_access_request(
            requester_person_key="b", requested_role_bundle="engineer_transform",
        )
        items = await access_service.list_access_requests()
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_requester(self):
        await access_service.create_access_request(
            requester_person_key="alice", requested_role_bundle="analyst_readonly",
        )
        await access_service.create_access_request(
            requester_person_key="bob", requested_role_bundle="analyst_readonly",
        )
        items = await access_service.list_access_requests(requester="alice")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_filter_by_state(self):
        await access_service.create_access_request(
            requester_person_key="user1",
            requested_role_bundle="analyst_readonly",
        )
        items = await access_service.list_access_requests(
            state=AccessRequestState.REQUESTED
        )
        assert len(items) == 1
        items = await access_service.list_access_requests(
            state=AccessRequestState.APPROVED
        )
        assert len(items) == 0
