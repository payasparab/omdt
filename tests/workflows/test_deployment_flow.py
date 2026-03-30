"""End-to-end deployment workflow test.

Tests: PR merge -> CI -> approval -> deploy -> smoke test -> record.
"""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import DeploymentState
from app.jobs import deployment_jobs
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


class TestDeploymentFlow:
    @pytest.mark.asyncio
    async def test_end_to_end_deployment(self):
        """Simulate a full deployment lifecycle."""
        # Track events
        succeeded_events = []
        async def on_succeeded(e): succeeded_events.append(e)
        subscribe("deployment.succeeded", on_succeeded)

        # 1. Create deployment (simulates PR merge triggering a deployment)
        deployment = await deploy_service.create_deployment(
            git_sha="abc123def456789",
            environment="staging",
            branch_or_tag="main",
            triggered_by_person_key="payas.parab",
        )
        assert deployment.state == DeploymentState.BUILD_PENDING

        # 2. CI passes (build_passed)
        deployment = await deploy_service.mark_build_passed(str(deployment.id))
        assert deployment.state == DeploymentState.DEPLOY_PENDING_APPROVAL

        # 3. Approval gate
        deployment = await deploy_service.approve_deployment(
            str(deployment.id), "payas.parab"
        )
        assert deployment.state == DeploymentState.DEPLOY_IN_PROGRESS

        # 4. Execute deployment
        deployment = await deploy_service.execute_deployment(str(deployment.id))
        assert deployment.state == DeploymentState.DEPLOY_SUCCEEDED

        # 5. Run smoke tests
        smoke_result = await deployment_jobs.post_deploy_smoke_test(str(deployment.id))
        assert smoke_result["status"] == "passed"

        # 6. Notify
        notify_result = await deployment_jobs.notify_deployment_result(
            str(deployment.id), "succeeded"
        )
        assert notify_result["status"] == "sent"

        # Verify events fired
        assert len(succeeded_events) == 1

        # Verify audit trail covers full lifecycle
        log = get_audit_log()
        event_names = [r["event_name"] for r in log]
        assert "deployment.created" in event_names
        assert "deployment.build_passed" in event_names
        assert "deployment.approved" in event_names
        assert "deployment.succeeded" in event_names
        assert "deployment.smoke_test_completed" in event_names
        assert "deployment.notification_sent" in event_names

    @pytest.mark.asyncio
    async def test_deployment_with_rollback(self):
        """Simulate deployment followed by rollback."""
        deployment = await deploy_service.create_deployment(
            git_sha="bad123",
            environment="production",
            branch_or_tag="release/1.2",
        )
        await deploy_service.mark_build_passed(str(deployment.id))
        await deploy_service.approve_deployment(str(deployment.id), "admin")
        await deploy_service.execute_deployment(str(deployment.id))

        # Discover issue, rollback
        deployment = await deploy_service.rollback_deployment(
            str(deployment.id),
            "Regression in user auth",
            actor="admin",
        )
        assert deployment.state == DeploymentState.ROLLED_BACK

        log = get_audit_log()
        assert any(r["event_name"] == "deployment.rolled_back" for r in log)

    @pytest.mark.asyncio
    async def test_deployment_requires_approval(self):
        """Cannot execute without approval."""
        deployment = await deploy_service.create_deployment(
            git_sha="skip123",
            environment="production",
        )
        await deploy_service.mark_build_passed(str(deployment.id))

        # Skip approval — try to execute directly
        result = await deploy_service.execute_deployment(str(deployment.id))
        # Should not have succeeded because state is DEPLOY_PENDING_APPROVAL, not DEPLOY_IN_PROGRESS
        assert result.state == DeploymentState.DEPLOY_PENDING_APPROVAL
