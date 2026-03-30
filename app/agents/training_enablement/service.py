"""Training/Enablement Agent — generates onboarding plans, guides, exercises, and FAQs."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.training_enablement.schemas import (
    Exercise,
    FollowUpPlan,
    KnowledgeCheck,
    OnboardingChecklist,
    OnboardingStep,
    TrainingEnablementInput,
    TrainingEnablementOutput,
    TrainingPlan,
    UnresolvedIssue,
)
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Role-based onboarding templates
# ---------------------------------------------------------------------------

_ROLE_OBJECTIVES: dict[str, list[str]] = {
    "data_analyst": [
        "Understand data warehouse schema and key tables",
        "Run basic SQL queries in Snowflake",
        "Navigate the BI dashboard platform",
        "Submit analysis requests through OMDT",
    ],
    "data_engineer": [
        "Set up local development environment",
        "Understand dbt project structure and conventions",
        "Run and debug pipeline jobs",
        "Deploy pipeline changes via CI/CD",
    ],
    "data_scientist": [
        "Access experiment tracking platform",
        "Understand feature store structure",
        "Run model training pipelines",
        "Register models in the model registry",
    ],
}

_DEFAULT_OBJECTIVES = [
    "Understand OMDT platform basics",
    "Navigate key tools and dashboards",
    "Submit requests and track work items",
    "Follow data governance policies",
]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _generate_onboarding_plan(
    audience_role: str, tool_scope: list[str]
) -> TrainingPlan:
    objectives = _ROLE_OBJECTIVES.get(audience_role, _DEFAULT_OBJECTIVES)
    steps = [
        OnboardingStep(
            step_number=1,
            title="Platform Overview",
            description="Introduction to OMDT and core concepts.",
            estimated_minutes=30,
        ),
        OnboardingStep(
            step_number=2,
            title="Tool Access Setup",
            description=f"Provision and configure access to: {', '.join(tool_scope) if tool_scope else 'core tools'}.",
            estimated_minutes=45,
        ),
        OnboardingStep(
            step_number=3,
            title="Guided Walkthrough",
            description="Hands-on walkthrough of key workflows.",
            estimated_minutes=60,
        ),
        OnboardingStep(
            step_number=4,
            title="Independent Exercise",
            description="Complete a practice task independently.",
            estimated_minutes=45,
        ),
    ]
    return TrainingPlan(
        audience_role=audience_role,
        tool_scope=tool_scope,
        learning_objectives=objectives,
        prerequisites=["Active account", "VPN access"],
        onboarding_steps=steps,
        completion_criteria=[
            "All onboarding steps completed",
            "Knowledge check passed with ≥80%",
            "Practice task submitted and reviewed",
        ],
        follow_up_actions=[
            "Schedule 1:1 with mentor after first week",
            "Review adoption metrics at 30 days",
        ],
    )


def _generate_setup_guide(tool_name: str, prerequisites: list[str]) -> str:
    prereqs = "\n".join(f"- {p}" for p in prerequisites) if prerequisites else "- None"
    return (
        f"# Setup Guide: {tool_name}\n\n"
        f"## Prerequisites\n{prereqs}\n\n"
        f"## Installation\n1. Install {tool_name} following the official documentation.\n"
        f"2. Configure credentials and connection settings.\n"
        f"3. Verify installation by running the health check.\n\n"
        f"## Configuration\n- Set environment variables as documented.\n"
        f"- Confirm connectivity to required services.\n\n"
        f"## Verification\n- Run `{tool_name.lower().replace(' ', '_')} --version` to confirm.\n"
    )


def _generate_faq(topic: str, common_issues: list[str]) -> str:
    faq_items = []
    for i, issue in enumerate(common_issues, 1):
        faq_items.append(
            f"### Q{i}: {issue}\n**A:** Please refer to the documentation or "
            f"contact the support channel for assistance with: {issue}\n"
        )
    if not faq_items:
        faq_items.append(
            f"### Q1: How do I get started with {topic}?\n"
            f"**A:** Begin with the onboarding guide and setup instructions.\n"
        )
    return f"# FAQ: {topic}\n\n" + "\n".join(faq_items)


def _generate_exercises(tool_name: str, skill_level: str) -> list[Exercise]:
    exercises = [
        Exercise(
            title=f"Getting Started with {tool_name}",
            skill_level="beginner",
            description=f"Complete a basic task using {tool_name}.",
            expected_outcome=f"Successfully execute a basic {tool_name} operation.",
            estimated_minutes=30,
        ),
    ]
    if skill_level in ("intermediate", "advanced"):
        exercises.append(Exercise(
            title=f"Intermediate {tool_name} Workflow",
            skill_level="intermediate",
            description=f"Build a multi-step workflow in {tool_name}.",
            expected_outcome="Working multi-step workflow with error handling.",
            estimated_minutes=60,
        ))
    if skill_level == "advanced":
        exercises.append(Exercise(
            title=f"Advanced {tool_name} Optimization",
            skill_level="advanced",
            description=f"Optimize and extend a {tool_name} process.",
            expected_outcome="Measurable performance improvement documented.",
            estimated_minutes=90,
        ))
    return exercises


def _generate_knowledge_checks(topic: str) -> list[KnowledgeCheck]:
    return [
        KnowledgeCheck(
            question=f"What is the primary purpose of {topic}?",
            expected_answer=f"The primary purpose of {topic} is documented in the onboarding guide.",
            topic=topic,
        ),
        KnowledgeCheck(
            question=f"List the key components of {topic}.",
            expected_answer="Key components are covered in the setup guide.",
            topic=topic,
        ),
        KnowledgeCheck(
            question=f"Describe a common troubleshooting step for {topic}.",
            expected_answer="Refer to the FAQ for common troubleshooting steps.",
            topic=topic,
        ),
    ]


def _generate_cheat_sheet(tool_name: str) -> str:
    return (
        f"# Cheat Sheet: {tool_name}\n\n"
        f"## Quick Commands\n"
        f"| Action | Command |\n"
        f"|--------|--------|\n"
        f"| Start | `{tool_name.lower().replace(' ', '_')} start` |\n"
        f"| Status | `{tool_name.lower().replace(' ', '_')} status` |\n"
        f"| Help | `{tool_name.lower().replace(' ', '_')} --help` |\n\n"
        f"## Tips\n"
        f"- Always check status before making changes.\n"
        f"- Use `--verbose` for detailed output.\n"
        f"- Refer to the full documentation for advanced usage.\n"
    )


def _create_follow_up_plan(user: str, completion_status: str) -> FollowUpPlan:
    next_steps = []
    unresolved = []
    if completion_status == "complete":
        next_steps = [
            "Schedule advanced training session",
            "Assign first independent task",
        ]
    elif completion_status == "partial":
        next_steps = [
            "Review incomplete modules",
            "Schedule catch-up session",
        ]
        unresolved = ["Some onboarding modules not completed"]
    else:
        next_steps = [
            "Restart onboarding from the beginning",
            "Assign a mentor for guided completion",
        ]
        unresolved = ["Onboarding not started or significantly incomplete"]
    return FollowUpPlan(
        user=user,
        completion_status=completion_status,
        next_steps=next_steps,
        unresolved_issues=unresolved,
    )


def _route_unresolved_issues(issues: list[str]) -> list[UnresolvedIssue]:
    return [
        UnresolvedIssue(
            issue=issue,
            suggested_owner="support_team",
            priority="medium",
        )
        for issue in issues
    ]


# ---------------------------------------------------------------------------
# Training/Enablement Agent
# ---------------------------------------------------------------------------

_VALID_ACTIONS = {
    "onboarding_plan",
    "setup_guide",
    "faq",
    "exercises",
    "knowledge_checks",
    "cheat_sheet",
    "follow_up",
    "route_issues",
}


class TrainingEnablementAgent(BaseAgent):
    """Generates training plans, setup guides, exercises, FAQs, and cheat sheets.

    Implements the training/enablement role from PRD section 10.6.
    """

    name = "training_enablement_agent"
    mission = (
        "Generate role-based onboarding plans, tool setup guides, FAQs, "
        "hands-on exercises, knowledge checks, and cheat sheets. Track "
        "adoption and route unresolved issues as work items."
    )
    allowed_tools = [
        "create_training_plan",
        "create_document",
        "create_exercise",
        "create_knowledge_check",
        "attach_artifact",
        "create_work_item",
        "request_handoff",
    ]
    required_inputs = ["action"]
    output_schema = TrainingEnablementOutput
    handoff_targets = ["data_pm", "head_of_data"]

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the requested training/enablement action."""
        inputs = context.input_data

        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        training_input = TrainingEnablementInput.model_validate(inputs)
        action = training_input.action

        if action not in _VALID_ACTIONS:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Unknown action: {action}. Valid: {sorted(_VALID_ACTIONS)}"],
            )

        output = TrainingEnablementOutput(action=action)

        if action == "onboarding_plan":
            role = training_input.audience_role or "general"
            plan = _generate_onboarding_plan(role, training_input.tool_scope)
            output.training_plan = plan
            output.onboarding_checklist = OnboardingChecklist(
                items=[s.title for s in plan.onboarding_steps],
                estimated_duration=f"{sum(s.estimated_minutes for s in plan.onboarding_steps)} minutes",
                required_tools=training_input.tool_scope,
            )

        elif action == "setup_guide":
            tool = training_input.tool_name or "Unknown Tool"
            output.document_content = _generate_setup_guide(
                tool, training_input.prerequisites
            )

        elif action == "faq":
            topic = training_input.topic or "General"
            output.document_content = _generate_faq(
                topic, training_input.common_issues
            )

        elif action == "exercises":
            tool = training_input.tool_name or "General"
            output.exercises = _generate_exercises(tool, training_input.skill_level)

        elif action == "knowledge_checks":
            topic = training_input.topic or "General"
            output.knowledge_checks = _generate_knowledge_checks(topic)

        elif action == "cheat_sheet":
            tool = training_input.tool_name or "General"
            output.document_content = _generate_cheat_sheet(tool)

        elif action == "follow_up":
            user = training_input.user or "unknown_user"
            status = training_input.completion_status or "not_started"
            output.follow_up_plan = _create_follow_up_plan(user, status)

        elif action == "route_issues":
            output.routed_issues = _route_unresolved_issues(training_input.issues)

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
