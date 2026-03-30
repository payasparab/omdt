"""Integration test: deployment request -> approval -> deploy -> smoke test -> record -> audit."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import DeploymentState
from app.services import deployments
from tests.conftest import FakeAdapter


@pytest.fixture(autouse=True)
def _clean():
    deployments.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    deployments.clear_store()
    clear_audit_log()
    clear_handlers()


class TestDeploymentPipeline:
    """Deployment request -> approval -> CI trigger -> deploy -> smoke test -> record -> audit."""

    @pytest.mark.asyncio
    async def test_full_deployment_lifecycle(self, fake_render_adapter: FakeAdapter) -> None:
        """End-to-end deployment from creation to success."""
        # 1. Create deployment
        dep = await deployments.create_deployment(
            git_sha="abc1234567890def",
            environment="staging",
            branch_or_tag="main",
            triggered_by_person_key="engineer@example.com",
        )
        assert dep.state == DeploymentState.BUILD_PENDING

        # 2. Mark build passed
        built = await deployments.mark_build_passed(str(dep.id))
        assert built.state == DeploymentState.DEPLOY_PENDING_APPROVAL

        # 3. Approve deployment
        approved = await deployments.approve_deployment(
            str(dep.id),
            approver="lead@example.com",
        )
        assert approved.state == DeploymentState.DEPLOY_IN_PROGRESS

        # 4. Execute deployment
        executed = await deployments.execute_deployment(
            str(dep.id),
            render_adapter=fake_render_adapter,
        )
        assert executed.state == DeploymentState.DEPLOY_SUCCEEDED
        assert executed.smoke_test_result == "passed"
        assert executed.completed_at is not None
        fake_render_adapter.assert_called("deploy_service")

    @pytest.mark.asyncio
    async def test_deployment_failure_recorded(self) -> None:
        """Failed deployment records failure state and audit."""
        failing_adapter = FakeAdapter()

        async def fail_execute(action, params):
            raise RuntimeError("Render deploy failed")

        failing_adapter.execute = fail_execute

        dep = await deployments.create_deployment(
            git_sha="deadbeef",
            environment="production",
        )
        await deployments.mark_build_passed(str(dep.id))
        await deployments.approve_deployment(str(dep.id), approver="lead@example.com")

        executed = await deployments.execute_deployment(
            str(dep.id),
            render_adapter=failing_adapter,
        )
        assert executed.state == DeploymentState.DEPLOY_FAILED
        assert "failed" in executed.smoke_test_result

    @pytest.mark.asyncio
    async def test_deployment_rollback(self, fake_render_adapter: FakeAdapter) -> None:
        """Rollback from a succeeded deployment."""
        dep = await deployments.create_deployment(
            git_sha="abc123",
            environment="production",
        )
        await deployments.mark_build_passed(str(dep.id))
        await deployments.approve_deployment(str(dep.id), approver="lead@example.com")
        await deployments.execute_deployment(str(dep.id), render_adapter=fake_render_adapter)

        rolled_back = await deployments.rollback_deployment(
            str(dep.id),
            reason="Regression detected",
            actor="oncall@example.com",
        )
        assert rolled_back.state == DeploymentState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_deployment_audit_trail(self, fake_render_adapter: FakeAdapter) -> None:
        """Full audit trail for deployment lifecycle."""
        dep = await deployments.create_deployment(
            git_sha="abc123",
            environment="staging",
            triggered_by_person_key="eng@example.com",
        )
        await deployments.mark_build_passed(str(dep.id))
        await deployments.approve_deployment(str(dep.id), approver="lead@example.com")
        await deployments.execute_deployment(str(dep.id), render_adapter=fake_render_adapter)

        audit = get_audit_log()
        event_names = [r["event_name"] for r in audit]
        assert "deployment.created" in event_names
        assert "deployment.build_passed" in event_names
        assert "deployment.approved" in event_names
        assert "deployment.succeeded" in event_names

    @pytest.mark.asyncio
    async def test_deployment_events_emitted(self, fake_render_adapter: FakeAdapter) -> None:
        """Verify domain events emitted during deployment."""
        events: list[str] = []
        for name in ["deployment.created", "deployment.build_passed", "deployment.approved",
                      "deployment.started", "deployment.succeeded"]:
            subscribe(name, lambda p, n=name: events.append(n))

        dep = await deployments.create_deployment(git_sha="abc123", environment="staging")
        await deployments.mark_build_passed(str(dep.id))
        await deployments.approve_deployment(str(dep.id), approver="lead@example.com")
        await deployments.execute_deployment(str(dep.id), render_adapter=fake_render_adapter)

        assert "deployment.created" in events
        assert "deployment.started" in events
        assert "deployment.succeeded" in events
