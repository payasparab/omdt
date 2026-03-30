"""Tests for deployment job helpers."""

import pytest
from unittest.mock import AsyncMock

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
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


class TestTriggerGithubCI:
    @pytest.mark.asyncio
    async def test_trigger_without_adapter(self):
        result = await deployment_jobs.trigger_github_ci("main", "ci.yml")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_trigger_with_adapter(self):
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={"run_id": "123"})

        result = await deployment_jobs.trigger_github_ci(
            "main", "ci.yml", github_adapter=mock_adapter
        )
        assert result["status"] == "triggered"
        assert result["workflow"] == "ci.yml"
        mock_adapter.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_writes_audit(self):
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={})

        await deployment_jobs.trigger_github_ci(
            "main", "ci.yml", github_adapter=mock_adapter
        )
        log = get_audit_log()
        assert any(r["event_name"] == "ci.triggered" for r in log)


class TestTriggerRenderDeploy:
    @pytest.mark.asyncio
    async def test_trigger_without_adapter(self):
        result = await deployment_jobs.trigger_render_deploy("svc-1", "abc123")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_trigger_with_adapter(self):
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={"deploy_id": "d1"})

        result = await deployment_jobs.trigger_render_deploy(
            "svc-1", "abc123", render_adapter=mock_adapter
        )
        assert result["status"] == "triggered"
        mock_adapter.execute.assert_called_once()


class TestPostDeploySmokeTest:
    @pytest.mark.asyncio
    async def test_smoke_test_passes(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        result = await deployment_jobs.post_deploy_smoke_test(str(d.id))
        assert result["status"] == "passed"
        assert len(result["checks"]) >= 1

    @pytest.mark.asyncio
    async def test_smoke_test_missing_deployment(self):
        result = await deployment_jobs.post_deploy_smoke_test("nonexistent")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_smoke_test_writes_audit(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deployment_jobs.post_deploy_smoke_test(str(d.id))
        log = get_audit_log()
        assert any(r["event_name"] == "deployment.smoke_test_completed" for r in log)


class TestNotifyDeploymentResult:
    @pytest.mark.asyncio
    async def test_notify_success(self):
        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        result = await deployment_jobs.notify_deployment_result(str(d.id), "succeeded")
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_notify_missing_deployment(self):
        result = await deployment_jobs.notify_deployment_result("nonexistent", "failed")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_notify_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("deployment.notification_sent", handler)

        d = await deploy_service.create_deployment(
            git_sha="abc123", environment="staging"
        )
        await deployment_jobs.notify_deployment_result(str(d.id), "succeeded")
        assert len(events) == 1
