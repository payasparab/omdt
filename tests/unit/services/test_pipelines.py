"""Tests for the pipeline service."""

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import PipelineType
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


class TestCreatePipeline:
    @pytest.mark.asyncio
    async def test_create_returns_pipeline(self):
        p = await pipeline_service.create_pipeline(
            pipeline_key="etl-users",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            description="User ETL pipeline",
        )
        assert p.pipeline_key == "etl-users"
        assert p.pipeline_type == PipelineType.SQL_TRANSFORMATION
        assert p.description == "User ETL pipeline"

    @pytest.mark.asyncio
    async def test_create_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("pipeline.created", handler)

        await pipeline_service.create_pipeline(
            pipeline_key="etl-orders",
            pipeline_type=PipelineType.DATA_INGESTION,
        )
        assert len(events) == 1
        assert events[0]["pipeline_key"] == "etl-orders"

    @pytest.mark.asyncio
    async def test_create_writes_audit(self):
        await pipeline_service.create_pipeline(
            pipeline_key="etl-test",
            pipeline_type=PipelineType.PYTHON_BATCH,
        )
        log = get_audit_log()
        assert any(r["event_name"] == "pipeline.created" for r in log)

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self):
        p = await pipeline_service.create_pipeline(
            pipeline_key="full-pipeline",
            pipeline_type=PipelineType.METRIC_REFRESH,
            description="Full pipeline",
            owner_person_key="payas.parab",
            inputs=["raw.users"],
            outputs=["analytics.user_metrics"],
            upstream_dependencies=["etl-users"],
            schedule="0 6 * * *",
            environment_targets=["staging", "production"],
            quality_checks=[{"type": "row_count", "min": 100}],
            rollback_notes="Re-run previous version",
            linked_linear_issue_id="LIN-123",
            alert_rules=[{"channel": "slack", "on": "failure"}],
        )
        assert p.inputs == ["raw.users"]
        assert p.outputs == ["analytics.user_metrics"]
        assert p.schedule == "0 6 * * *"
        assert len(p.environment_targets) == 2


class TestGetPipeline:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        p = await pipeline_service.create_pipeline(
            pipeline_key="etl-get",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        found = await pipeline_service.get_pipeline("etl-get")
        assert found is not None
        assert found.id == p.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        assert await pipeline_service.get_pipeline("nonexistent") is None


class TestListPipelines:
    @pytest.mark.asyncio
    async def test_list_all(self):
        await pipeline_service.create_pipeline(
            pipeline_key="a", pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        await pipeline_service.create_pipeline(
            pipeline_key="b", pipeline_type=PipelineType.PYTHON_BATCH,
        )
        items = await pipeline_service.list_pipelines()
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        await pipeline_service.create_pipeline(
            pipeline_key="sql1", pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        await pipeline_service.create_pipeline(
            pipeline_key="py1", pipeline_type=PipelineType.PYTHON_BATCH,
        )
        items = await pipeline_service.list_pipelines(
            pipeline_type=PipelineType.SQL_TRANSFORMATION
        )
        assert len(items) == 1
        assert items[0].pipeline_key == "sql1"

    @pytest.mark.asyncio
    async def test_filter_by_owner(self):
        await pipeline_service.create_pipeline(
            pipeline_key="owned",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            owner_person_key="alice",
        )
        await pipeline_service.create_pipeline(
            pipeline_key="other",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            owner_person_key="bob",
        )
        items = await pipeline_service.list_pipelines(owner="alice")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_filter_by_environment(self):
        await pipeline_service.create_pipeline(
            pipeline_key="prod",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            environment_targets=["production"],
        )
        await pipeline_service.create_pipeline(
            pipeline_key="staging",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            environment_targets=["staging"],
        )
        items = await pipeline_service.list_pipelines(environment="production")
        assert len(items) == 1
        assert items[0].pipeline_key == "prod"


class TestUpdatePipeline:
    @pytest.mark.asyncio
    async def test_update_fields(self):
        await pipeline_service.create_pipeline(
            pipeline_key="update-me",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            description="old",
        )
        updated = await pipeline_service.update_pipeline(
            "update-me", actor="user1", description="new"
        )
        assert updated is not None
        assert updated.description == "new"

    @pytest.mark.asyncio
    async def test_update_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("pipeline.updated", handler)

        await pipeline_service.create_pipeline(
            pipeline_key="upd",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        await pipeline_service.update_pipeline("upd", actor="user1", description="x")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_update_missing_returns_none(self):
        result = await pipeline_service.update_pipeline("nope", description="x")
        assert result is None


class TestRecordPipelineRun:
    @pytest.mark.asyncio
    async def test_record_run(self):
        await pipeline_service.create_pipeline(
            pipeline_key="run-test",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        run = await pipeline_service.record_pipeline_run(
            "run-test", status="completed", duration_seconds=42.5
        )
        assert run is not None
        assert run.status == "completed"
        assert run.duration_seconds == 42.5

    @pytest.mark.asyncio
    async def test_record_run_emits_events(self):
        started = []
        completed = []
        async def on_start(e): started.append(e)
        async def on_complete(e): completed.append(e)
        subscribe("pipeline.run_started", on_start)
        subscribe("pipeline.run_completed", on_complete)

        await pipeline_service.create_pipeline(
            pipeline_key="events",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        await pipeline_service.record_pipeline_run("events", status="completed")
        assert len(started) == 1
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_record_run_missing_pipeline(self):
        run = await pipeline_service.record_pipeline_run("missing", status="completed")
        assert run is None

    @pytest.mark.asyncio
    async def test_get_pipeline_runs(self):
        await pipeline_service.create_pipeline(
            pipeline_key="multi-run",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
        )
        await pipeline_service.record_pipeline_run("multi-run", status="completed")
        await pipeline_service.record_pipeline_run("multi-run", status="failed")
        runs = await pipeline_service.get_pipeline_runs("multi-run")
        assert len(runs) == 2


class TestDependencyGraph:
    @pytest.mark.asyncio
    async def test_simple_graph(self):
        await pipeline_service.create_pipeline(
            pipeline_key="upstream",
            pipeline_type=PipelineType.DATA_INGESTION,
        )
        await pipeline_service.create_pipeline(
            pipeline_key="downstream",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            upstream_dependencies=["upstream"],
        )
        graph = await pipeline_service.get_pipeline_dependencies("downstream")
        assert "downstream" in graph
        assert "upstream" in graph["downstream"]
        assert "upstream" in graph
        assert graph["upstream"] == []

    @pytest.mark.asyncio
    async def test_missing_pipeline_returns_empty(self):
        graph = await pipeline_service.get_pipeline_dependencies("nonexistent")
        assert graph == {}

    @pytest.mark.asyncio
    async def test_chain_dependencies(self):
        await pipeline_service.create_pipeline(
            pipeline_key="a", pipeline_type=PipelineType.DATA_INGESTION,
        )
        await pipeline_service.create_pipeline(
            pipeline_key="b",
            pipeline_type=PipelineType.SQL_TRANSFORMATION,
            upstream_dependencies=["a"],
        )
        await pipeline_service.create_pipeline(
            pipeline_key="c",
            pipeline_type=PipelineType.METRIC_REFRESH,
            upstream_dependencies=["b"],
        )
        graph = await pipeline_service.get_pipeline_dependencies("c")
        assert set(graph.keys()) == {"a", "b", "c"}
