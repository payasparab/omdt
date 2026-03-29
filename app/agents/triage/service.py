"""Triage Agent — classifies intake, identifies missing info, proposes routing."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.triage.schemas import (
    REQUIRED_CLARIFICATION_FIELDS,
    ClarificationItem,
    TriageInput,
    TriageOutput,
)
from app.domain.enums import CanonicalState, Priority, WorkItemType


# ---------------------------------------------------------------------------
# Keyword-based route classification
# ---------------------------------------------------------------------------

_ROUTE_KEYWORDS: dict[str, list[str]] = {
    "analysis_request": ["analysis", "analyze", "report", "insight", "metric", "kpi"],
    "dashboard_request": ["dashboard", "visualiz", "chart", "graph", "lovable"],
    "pipeline_request": ["pipeline", "etl", "ingestion", "transformation", "dbt", "airflow"],
    "data_model_request": ["data model", "schema", "dbml", "erd", "entity", "table design"],
    "data_science_request": ["model", "predict", "machine learning", "ml", "experiment", "feature"],
    "paper_review_request": ["paper", "research", "literature", "academic", "arxiv", "journal"],
    "documentation_request": ["document", "runbook", "release note", "memo", "sop", "guide"],
    "training_request": ["training", "onboard", "enablement", "learning", "walkthrough"],
    "access_request": ["access", "permission", "role", "grant", "snowflake role", "provision"],
    "bug_or_incident": ["bug", "incident", "error", "broken", "fix", "outage", "failure"],
    "vendor_or_procurement": ["vendor", "cost", "procure", "license", "finops", "budget"],
    "status_or_reporting": ["status", "update", "progress", "standup", "weekly"],
}

# Questions to ask for each missing clarification field
_CLARIFICATION_QUESTIONS: dict[str, str] = {
    "business_goal": "What is the business goal or outcome you are trying to achieve?",
    "decision_or_use_case": "What decision or use case will this support?",
    "requested_output": "What output do you need (e.g. dashboard, report, pipeline, model)?",
    "expected_audience": "Who is the intended audience for this deliverable?",
    "urgency": "When do you need this by, and how urgent is it?",
    "source_data": "What source data or systems are involved?",
    "system_or_environment": "Which systems or environments are relevant (e.g. Snowflake, production)?",
    "owner_or_approver": "Who is the owner or approver for this work?",
}


def _classify_route(text: str) -> tuple[str, float]:
    """Score text against keyword routes, return (route_key, confidence)."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for route, keywords in _ROUTE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[route] = score

    if not scores:
        return "unknown_needs_clarification", 0.3

    best_route = max(scores, key=scores.get)  # type: ignore[arg-type]
    max_score = scores[best_route]
    total_keywords = len(_ROUTE_KEYWORDS[best_route])
    confidence = min(0.5 + (max_score / total_keywords) * 0.5, 1.0)
    return best_route, round(confidence, 2)


def _detect_missing_fields(input_data: dict) -> list[str]:
    """Return clarification field names not present or empty in input_data."""
    missing: list[str] = []
    for field in REQUIRED_CLARIFICATION_FIELDS:
        value = input_data.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def _suggest_priority(text: str) -> Priority:
    """Heuristic priority based on keywords."""
    lower = text.lower()
    if any(w in lower for w in ("urgent", "critical", "asap", "emergency", "outage")):
        return Priority.CRITICAL
    if any(w in lower for w in ("high priority", "important", "blocking")):
        return Priority.HIGH
    if any(w in lower for w in ("low priority", "nice to have", "backlog", "when possible")):
        return Priority.LOW
    return Priority.MEDIUM


def _route_to_work_item_type(route_key: str) -> WorkItemType:
    """Map a route_key string to the corresponding WorkItemType enum."""
    try:
        return WorkItemType(route_key)
    except ValueError:
        return WorkItemType.UNKNOWN_NEEDS_CLARIFICATION


def _determine_next_state(missing_fields: list[str]) -> CanonicalState:
    """Choose the recommended next canonical state."""
    if missing_fields:
        return CanonicalState.NEEDS_CLARIFICATION
    return CanonicalState.READY_FOR_PRD


def _normalize_title(subject: str | None, body: str) -> str:
    """Produce a normalized title from subject or first line of body."""
    if subject and subject.strip():
        return subject.strip()[:120]
    first_line = body.strip().split("\n")[0]
    return first_line[:120] if first_line else "Untitled request"


def _determine_required_agents(route_key: str) -> list[str]:
    """Return the agent names needed for this route."""
    from app.agents.routing import ROUTE_TO_AGENT

    primary = ROUTE_TO_AGENT.get(route_key)
    agents: list[str] = []
    if primary and primary != "triage_agent":
        agents.append(primary)
    # Always include data_pm for PRD-worthy routes
    prd_routes = {
        "analysis_request", "dashboard_request", "pipeline_request",
        "data_model_request", "data_science_request",
    }
    if route_key in prd_routes and "data_pm" not in agents:
        agents.append("data_pm")
    return agents


# ---------------------------------------------------------------------------
# Triage Agent
# ---------------------------------------------------------------------------

class TriageAgent(BaseAgent):
    """Classifies intake, identifies missing info, proposes routing.

    Implements the triage specification from PRD section 10.3.
    """

    name = "triage_agent"
    mission = (
        "Convert raw requests into structured work items, identify "
        "ambiguity, gather missing information, choose a preliminary "
        "route, and initiate the PRD/feedback loop."
    )
    allowed_tools = [
        "create_draft_work_item",
        "create_conversation_thread",
        "update_conversation_thread",
        "ask_clarification",
        "create_linear_issue",
        "update_linear_issue",
        "attach_artifact",
        "request_data_pm_handoff",
    ]
    required_inputs = ["message_body"]
    output_schema = TriageOutput
    handoff_targets = ["data_pm", "head_of_data"]

    async def execute(self, context: AgentContext) -> AgentResult:
        """Run triage classification on the provided intake data."""
        inputs = context.input_data

        # Validate we have the minimum input
        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        # Parse input
        triage_input = TriageInput.model_validate(inputs)
        full_text = f"{triage_input.subject or ''} {triage_input.message_body}"

        # Classify route
        route_key, confidence = _classify_route(full_text)

        # Detect missing info
        missing_fields = _detect_missing_fields(inputs)

        # Build clarification questions (minimum next-best only)
        questions: list[ClarificationItem] = []
        for field in missing_fields[:3]:  # max 3 questions at a time
            q = _CLARIFICATION_QUESTIONS.get(field)
            if q:
                questions.append(ClarificationItem(field_name=field, question=q))

        # Determine priority, type, next state
        priority = _suggest_priority(full_text)
        work_item_type = _route_to_work_item_type(route_key)
        next_state = _determine_next_state(missing_fields)
        normalized_title = _normalize_title(triage_input.subject, triage_input.message_body)
        required_agents = _determine_required_agents(route_key)

        # Build output
        triage_output = TriageOutput(
            normalized_title=normalized_title,
            work_item_type=work_item_type,
            priority=priority,
            route_key=route_key,
            confidence=confidence,
            required_agents=required_agents,
            missing_info_checklist=missing_fields,
            clarification_questions=questions,
            linear_sync_intent=True,
            recommended_next_state=next_state,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=triage_output.model_dump(),
            prompt_version=None,
        )
