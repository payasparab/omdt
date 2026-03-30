"""Tests for the costing service."""

import pytest
from uuid import uuid4

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.services import costing as costing_service


@pytest.fixture(autouse=True)
def _clean():
    costing_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    costing_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestRecordCostEvent:
    @pytest.mark.asyncio
    async def test_record_cost(self):
        event = await costing_service.record_cost_event(
            tool_name="snowflake",
            usage_quantity=100.0,
            usage_unit="credits",
            estimated_cost_usd=2.50,
        )
        assert event.tool_name == "snowflake"
        assert event.usage_quantity == 100.0
        assert event.estimated_cost_usd == 2.50

    @pytest.mark.asyncio
    async def test_record_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("cost.recorded", handler)

        await costing_service.record_cost_event(
            tool_name="render",
            usage_quantity=1.0,
            usage_unit="hours",
        )
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_record_writes_audit(self):
        await costing_service.record_cost_event(
            tool_name="github",
            usage_quantity=500.0,
            usage_unit="minutes",
        )
        log = get_audit_log()
        assert any(r["event_name"] == "cost.recorded" for r in log)


class TestRecordToolUsage:
    @pytest.mark.asyncio
    async def test_record_usage(self):
        event = await costing_service.record_tool_usage(
            tool_name="snowflake",
            action="run_query",
            duration_ms=1500,
            success=True,
        )
        assert event.tool_name == "snowflake"
        assert event.action == "run_query"
        assert event.duration_ms == 1500

    @pytest.mark.asyncio
    async def test_record_failed_usage(self):
        event = await costing_service.record_tool_usage(
            tool_name="render",
            action="deploy",
            success=False,
            error_message="timeout",
        )
        assert event.success is False
        assert event.error_message == "timeout"


class TestGetProjectCosts:
    @pytest.mark.asyncio
    async def test_project_cost_summary(self):
        project_id = uuid4()
        await costing_service.record_cost_event(
            tool_name="snowflake",
            usage_quantity=100.0,
            usage_unit="credits",
            estimated_cost_usd=2.50,
            project_id=project_id,
        )
        await costing_service.record_cost_event(
            tool_name="render",
            usage_quantity=10.0,
            usage_unit="hours",
            estimated_cost_usd=1.00,
            project_id=project_id,
        )

        summary = await costing_service.get_project_costs(str(project_id))
        assert summary["total_cost_usd"] == 3.50
        assert summary["event_count"] == 2
        assert summary["by_tool"]["snowflake"] == 2.50
        assert summary["by_tool"]["render"] == 1.00


class TestGetToolCosts:
    @pytest.mark.asyncio
    async def test_tool_cost_summary(self):
        await costing_service.record_cost_event(
            tool_name="snowflake",
            usage_quantity=100.0,
            usage_unit="credits",
            estimated_cost_usd=2.50,
        )
        await costing_service.record_cost_event(
            tool_name="snowflake",
            usage_quantity=200.0,
            usage_unit="credits",
            estimated_cost_usd=5.00,
        )

        summary = await costing_service.get_tool_costs("snowflake")
        assert summary["total_cost_usd"] == 7.50
        assert summary["total_quantity"] == 300.0
        assert summary["event_count"] == 2


class TestAttributeCost:
    @pytest.mark.asyncio
    async def test_attribute_to_project(self):
        event = await costing_service.record_cost_event(
            tool_name="snowflake",
            usage_quantity=100.0,
            usage_unit="credits",
        )
        project_id = str(uuid4())
        attributed = await costing_service.attribute_cost(str(event.id), project_id)
        assert attributed is not None
        assert str(attributed.project_id) == project_id

    @pytest.mark.asyncio
    async def test_attribute_missing_event(self):
        result = await costing_service.attribute_cost("nonexistent", str(uuid4()))
        assert result is None

    @pytest.mark.asyncio
    async def test_attribute_writes_audit(self):
        event = await costing_service.record_cost_event(
            tool_name="test",
            usage_quantity=1.0,
            usage_unit="unit",
        )
        await costing_service.attribute_cost(str(event.id), str(uuid4()))
        log = get_audit_log()
        assert any(r["event_name"] == "cost.attributed" for r in log)
