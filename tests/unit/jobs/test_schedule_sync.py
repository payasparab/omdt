"""Tests for the schedule sync bridge."""

import pytest
from unittest.mock import AsyncMock

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import PipelineType
from app.jobs import schedule_sync
from app.services import pipelines as pipeline_service


@pytest.fixture(autouse=True)
def _clean():
    pipeline_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    pipeline_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestSyncSchedules:
    @pytest.mark.asyncio
    async def test_sync_no_pipelines(self):
        result = await schedule_sync.sync_schedules()
        assert result["total"] == 0
        assert result["created"] == []

    @pytest.mark.asyncio
    async def test_sync_skips_without_adapter(self):
        await pipeline_service.create_pipeline(
            pipeline_key="scheduled",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            schedule="0 6 * * *",
        )
        result = await schedule_sync.sync_schedules()
        assert result["total"] == 1
        assert result["skipped"] == ["scheduled"]

    @pytest.mark.asyncio
    async def test_sync_creates_with_adapter(self):
        await pipeline_service.create_pipeline(
            pipeline_key="cron-test",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            schedule="0 8 * * *",
        )
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={"cron_id": "c1"})

        result = await schedule_sync.sync_schedules(render_adapter=mock_adapter)
        assert result["total"] == 1
        assert "cron-test" in result["created"]

    @pytest.mark.asyncio
    async def test_sync_skips_unscheduled(self):
        await pipeline_service.create_pipeline(
            pipeline_key="no-schedule",
            pipeline_type=PipelineType.PYTHON_BATCH,
        )
        result = await schedule_sync.sync_schedules()
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_sync_writes_audit(self):
        await pipeline_service.create_pipeline(
            pipeline_key="audit-test",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            schedule="0 6 * * *",
        )
        await schedule_sync.sync_schedules()
        log = get_audit_log()
        assert any(r["event_name"] == "schedule.sync_completed" for r in log)


class TestCreateRenderCron:
    @pytest.mark.asyncio
    async def test_create_cron_with_adapter(self):
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={"cron_id": "c1"})

        result = await schedule_sync.create_render_cron(
            "my-pipeline", "0 6 * * *", render_adapter=mock_adapter
        )
        assert result["action"] == "created"
        mock_adapter.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_cron_without_adapter(self):
        result = await schedule_sync.create_render_cron("my-pipeline", "0 6 * * *")
        assert result["action"] == "skipped"


class TestUpdateRenderCron:
    @pytest.mark.asyncio
    async def test_update_cron_with_adapter(self):
        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value={"ok": True})

        result = await schedule_sync.update_render_cron(
            "my-pipeline", "0 8 * * *", render_adapter=mock_adapter
        )
        assert result["action"] == "updated"

    @pytest.mark.asyncio
    async def test_update_cron_without_adapter(self):
        result = await schedule_sync.update_render_cron("my-pipeline", "0 8 * * *")
        assert result["action"] == "skipped"
