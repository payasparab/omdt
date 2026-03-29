"""Agent routing — maps route keys and work item types to agents."""
from __future__ import annotations

from app.domain.enums import WorkItemType


# ---------------------------------------------------------------------------
# Route key -> agent mapping (§10.3 / §11.7)
# ---------------------------------------------------------------------------

ROUTE_TO_AGENT: dict[str, str] = {
    "analysis_request": "data_analyst",
    "dashboard_request": "data_analyst",
    "pipeline_request": "data_engineer",
    "data_model_request": "data_architect",
    "data_science_request": "data_scientist",
    "paper_review_request": "academic_research_agent",
    "documentation_request": "technical_writer_agent",
    "training_request": "training_enablement_agent",
    "access_request": "access_security_agent",
    "bug_or_incident": "data_engineer",
    "vendor_or_procurement": "vendor_finops_agent",
    "status_or_reporting": "data_pmo",
    "unknown_needs_clarification": "triage_agent",
}

# WorkItemType enum -> agent (convenience mapping)
WORK_ITEM_TYPE_TO_AGENT: dict[WorkItemType, str] = {
    WorkItemType.ANALYSIS_REQUEST: "data_analyst",
    WorkItemType.DASHBOARD_REQUEST: "data_analyst",
    WorkItemType.PIPELINE_REQUEST: "data_engineer",
    WorkItemType.DATA_MODEL_REQUEST: "data_architect",
    WorkItemType.DATA_SCIENCE_REQUEST: "data_scientist",
    WorkItemType.PAPER_REVIEW_REQUEST: "academic_research_agent",
    WorkItemType.DOCUMENTATION_REQUEST: "technical_writer_agent",
    WorkItemType.TRAINING_REQUEST: "training_enablement_agent",
    WorkItemType.ACCESS_REQUEST: "access_security_agent",
    WorkItemType.BUG_OR_INCIDENT: "data_engineer",
    WorkItemType.VENDOR_OR_PROCUREMENT: "vendor_finops_agent",
    WorkItemType.STATUS_OR_REPORTING: "data_pmo",
    WorkItemType.UNKNOWN_NEEDS_CLARIFICATION: "triage_agent",
}

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.6


def route_to_agent(
    route_key: str,
    confidence: float | None = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> str:
    """Determine which agent should handle a work item based on route_key.

    If *confidence* is provided and falls below *threshold*, the route
    defaults to ``triage_agent`` (unknown_needs_clarification).

    Raises:
        ValueError: If *route_key* is not in the known mapping.
    """
    if confidence is not None and confidence < threshold:
        return "triage_agent"

    agent = ROUTE_TO_AGENT.get(route_key)
    if agent is None:
        raise ValueError(f"Unknown route_key: '{route_key}'")
    return agent


def route_work_item_type(work_item_type: WorkItemType) -> str:
    """Map a WorkItemType enum to the responsible agent name."""
    agent = WORK_ITEM_TYPE_TO_AGENT.get(work_item_type)
    if agent is None:
        return "triage_agent"
    return agent
