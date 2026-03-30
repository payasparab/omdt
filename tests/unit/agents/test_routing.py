"""Tests for app.agents.routing — route_to_agent, route_work_item_type."""
from __future__ import annotations

import pytest

from app.agents.routing import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    ROUTE_TO_AGENT,
    WORK_ITEM_TYPE_TO_AGENT,
    route_to_agent,
    route_work_item_type,
)
from app.domain.enums import WorkItemType


class TestRouteToAgent:
    @pytest.mark.parametrize("route_key,expected_agent", list(ROUTE_TO_AGENT.items()))
    def test_all_route_keys_resolve(self, route_key: str, expected_agent: str) -> None:
        agent = route_to_agent(route_key, confidence=1.0)
        assert agent == expected_agent

    def test_unknown_route_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown route_key"):
            route_to_agent("completely_unknown")

    def test_low_confidence_defaults_to_triage(self) -> None:
        agent = route_to_agent("analysis_request", confidence=0.3)
        assert agent == "triage_agent"

    def test_confidence_at_threshold_passes(self) -> None:
        agent = route_to_agent(
            "analysis_request",
            confidence=DEFAULT_CONFIDENCE_THRESHOLD,
        )
        assert agent == "data_analyst"

    def test_confidence_just_below_threshold_defaults(self) -> None:
        agent = route_to_agent(
            "pipeline_request",
            confidence=DEFAULT_CONFIDENCE_THRESHOLD - 0.01,
        )
        assert agent == "triage_agent"

    def test_no_confidence_provided_routes_normally(self) -> None:
        agent = route_to_agent("access_request")
        assert agent == "access_security_agent"

    def test_custom_threshold(self) -> None:
        agent = route_to_agent("pipeline_request", confidence=0.5, threshold=0.8)
        assert agent == "triage_agent"

    def test_unknown_needs_clarification_routes_to_triage(self) -> None:
        agent = route_to_agent("unknown_needs_clarification")
        assert agent == "triage_agent"


class TestRouteWorkItemType:
    @pytest.mark.parametrize(
        "work_type,expected",
        list(WORK_ITEM_TYPE_TO_AGENT.items()),
    )
    def test_all_work_item_types_mapped(
        self, work_type: WorkItemType, expected: str
    ) -> None:
        assert route_work_item_type(work_type) == expected

    def test_every_work_item_type_has_mapping(self) -> None:
        for wt in WorkItemType:
            agent = route_work_item_type(wt)
            assert isinstance(agent, str)
            assert len(agent) > 0


class TestRouteMappingCompleteness:
    def test_all_work_item_type_values_in_route_map(self) -> None:
        """Every WorkItemType.value should be a key in ROUTE_TO_AGENT."""
        for wt in WorkItemType:
            assert wt.value in ROUTE_TO_AGENT, f"{wt.value} missing from ROUTE_TO_AGENT"

    def test_route_map_has_18_entries(self) -> None:
        assert len(ROUTE_TO_AGENT) == 18
