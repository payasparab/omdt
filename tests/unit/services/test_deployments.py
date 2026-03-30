"""Tests for the deployment service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import DeploymentState
from app.services import deployments as deploy_service


@pytest.fixture(autouse=True)
def _clean():
    deploy_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    deploy_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestCreateDeployment:
    @pytest.mark.asyncio
    async def test_create_returns_deployment(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123def456",
            environment="staging",
            branch_or_tag="main",
        )
        assert d.git_sha == "abc123def456"
        assert d.environment == "staging"
        assert d.state == DeploymentState.BUILD_PENDING

    @pytest.mark.asyncio
    async def test_create_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("deployment.created", handler)

        await deploy_service.create_deployment(
            git_sha="abc123", environment="production"
        )
        assert len(events) == 1
        assert events[0]["git_sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_create_writes_audit(self):
        await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        log = get_audit_log()
        assert any(r["event_name"] == "deployment.created" for r in log)


class TestDeploymentLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test: create -> build_passed -> approve -> execute -> succeed."""
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        assert d.state == DeploymentState.BUILD_PENDING

        # Build passes
        d = await deploy_service.mark_build_passed(str(d.id))
        assert d.state == DeploymentState.DEPLOY_PENDING_APPROVAL

        # Approve
        d = await deploy_service.approve_deployment(str(d.id), "admin")
        assert d.state == DeploymentState.DEPLOY_IN_PROGRESS

        # Execute
        d = await deploy_service.execute_deployment(str(d.id))
        assert d.state == DeploymentState.DEPLOY_SUCCEEDED
        assert d.smoke_test_result == "passed"
        assert d.completed_at is not None

    @pytest.mark.asyncio
    async def test_approval_gate_enforced(self):
        """Deployment can't be executed without approval."""
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        # Try to execute without approval — state is BUILD_PENDING, not DEPLOY_IN_PROGRESS
        result = await deploy_service.execute_deployment(str(d.id))
        assert result.state == DeploymentState.BUILD_PENDING

    @pytest.mark.asyncio
    async def test_approve_requires_build_passed(self):
        """Approval only works on BUILD_PASSED or DEPLOY_PENDING_APPROVAL."""
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        # Try to approve while still BUILD_PENDING
        result = await deploy_service.approve_deployment(str(d.id), "admin")
        assert result.state == DeploymentState.BUILD_PENDING


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_succeeded_deployment(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deploy_service.mark_build_passed(str(d.id))
        await deploy_service.approve_deployment(str(d.id), "admin")
        await deploy_service.execute_deployment(str(d.id))

        d = await deploy_service.rollback_deployment(
            str(d.id), "Found regression", actor="admin"
        )
        assert d.state == DeploymentState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_emits_events(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("deployment.rolled_back", handler)

        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deploy_service.mark_build_passed(str(d.id))
        await deploy_service.approve_deployment(str(d.id), "admin")
        await deploy_service.execute_deployment(str(d.id))
        await deploy_service.rollback_deployment(str(d.id), "bug")

        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_rollback_writes_audit(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deploy_service.mark_build_passed(str(d.id))
        await deploy_service.approve_deployment(str(d.id), "admin")
        await deploy_service.execute_deployment(str(d.id))
        await deploy_service.rollback_deployment(str(d.id), "issue")

        log = get_audit_log()
        assert any(r["event_name"] == "deployment.rolled_back" for r in log)


class TestGetDeployment:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        found = await deploy_service.get_deployment(str(d.id))
        assert found is not None
        assert found.id == d.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        assert await deploy_service.get_deployment("nonexistent") is None


class TestListDeployments:
    @pytest.mark.asyncio
    async def test_list_all(self):
        await deploy_service.create_deployment(
            git_sha="a", environment="staging"
        )
        await deploy_service.create_deployment(
            git_sha="b", environment="production"
        )
        items = await deploy_service.list_deployments()
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_environment(self):
        await deploy_service.create_deployment(
            git_sha="a", environment="staging"
        )
        await deploy_service.create_deployment(
            git_sha="b", environment="production"
        )
        items = await deploy_service.list_deployments(environment="staging")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_filter_by_state(self):
        await deploy_service.create_deployment(
            git_sha="a", environment="staging"
        )
        items = await deploy_service.list_deployments(
            state=DeploymentState.BUILD_PENDING
        )
        assert len(items) == 1
        items = await deploy_service.list_deployments(
            state=DeploymentState.DEPLOY_SUCCEEDED
        )
        assert len(items) == 0


class TestAuditTrail:
    @pytest.mark.asyncio
    async def test_full_lifecycle_audit_trail(self):
        """Every state transition should produce audit records."""
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deploy_service.mark_build_passed(str(d.id))
        await deploy_service.approve_deployment(str(d.id), "admin")
        await deploy_service.execute_deployment(str(d.id))

        log = get_audit_log()
        event_names = [r["event_name"] for r in log]
        assert "deployment.created" in event_names
        assert "deployment.build_passed" in event_names
        assert "deployment.approved" in event_names
        assert "deployment.succeeded" in event_names
