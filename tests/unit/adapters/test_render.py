"""Unit tests for the Render adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.render import RenderAdapter
from app.adapters.base import AdapterError
from tests.fixtures.render_responses import (
    VALID_CONFIG,
    DEPLOY_RESPONSE,
    CREATE_SERVICE_RESPONSE,
    DEPLOY_LOGS_RESPONSE,
    SERVICE_STATUS_RESPONSE,
)


@pytest.fixture
def adapter() -> RenderAdapter:
    return RenderAdapter(config=VALID_CONFIG.copy())


def _mock_api(response: dict[str, Any]):
    return patch.object(
        RenderAdapter, "_api_request", new_callable=AsyncMock, return_value=response
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid(self, adapter: RenderAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        a = RenderAdapter(config={})
        with pytest.raises(AdapterError, match="api_key"):
            await a.validate_config()


class TestDeployService:
    @pytest.mark.asyncio
    async def test_deploys(self, adapter: RenderAdapter):
        with _mock_api(DEPLOY_RESPONSE):
            result = await adapter.execute(
                "deploy_service", {"service_id": "srv_01"}
            )
            assert result["deploy_id"] == "dep_01"
            assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_missing_service_id(self, adapter: RenderAdapter):
        with pytest.raises(AdapterError, match="service_id"):
            await adapter.execute("deploy_service", {})


class TestRestartWorker:
    @pytest.mark.asyncio
    async def test_restarts(self, adapter: RenderAdapter):
        with _mock_api({"status": "ok"}):
            result = await adapter.execute(
                "restart_worker", {"service_id": "srv_01"}
            )
            assert result["restarted"] is True


class TestCronJobs:
    @pytest.mark.asyncio
    async def test_create_cron_job(self, adapter: RenderAdapter):
        with _mock_api(CREATE_SERVICE_RESPONSE):
            result = await adapter.execute(
                "create_cron_job",
                {
                    "name": "daily-sync",
                    "schedule": "0 8 * * *",
                    "command": "python -m app.jobs.sync",
                },
            )
            assert result["created"] is True
            assert result["name"] == "daily-sync"

    @pytest.mark.asyncio
    async def test_create_cron_missing_fields(self, adapter: RenderAdapter):
        with pytest.raises(AdapterError, match="requires"):
            await adapter.execute("create_cron_job", {"name": "x"})

    @pytest.mark.asyncio
    async def test_update_cron_job(self, adapter: RenderAdapter):
        with _mock_api({"service": {"id": "srv_cron_01"}}):
            result = await adapter.execute(
                "update_cron_job",
                {"service_id": "srv_cron_01", "schedule": "0 9 * * *"},
            )
            assert result["updated"] is True


class TestGetDeployLogs:
    @pytest.mark.asyncio
    async def test_gets_logs(self, adapter: RenderAdapter):
        with _mock_api(DEPLOY_LOGS_RESPONSE):
            result = await adapter.execute(
                "get_deploy_logs",
                {"service_id": "srv_01", "deploy_id": "dep_01"},
            )
            assert len(result["logs"]) == 2

    @pytest.mark.asyncio
    async def test_missing_fields(self, adapter: RenderAdapter):
        with pytest.raises(AdapterError, match="requires"):
            await adapter.execute("get_deploy_logs", {"service_id": "s"})


class TestGetServiceStatus:
    @pytest.mark.asyncio
    async def test_gets_status(self, adapter: RenderAdapter):
        with _mock_api(SERVICE_STATUS_RESPONSE):
            result = await adapter.execute(
                "get_service_status", {"service_id": "srv_01"}
            )
            assert result["name"] == "omdt-api"
            assert result["status"] == "running"
