"""Training/Enablement Agent input/output schemas per PRD section 10.6."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.ids import generate_id


class OnboardingStep(BaseModel):
    """A single step in an onboarding plan."""

    step_number: int
    title: str
    description: str = ""
    estimated_minutes: int = 30


class Exercise(BaseModel):
    """A hands-on exercise for training."""

    exercise_id: str = Field(default_factory=generate_id)
    title: str
    skill_level: str = "beginner"  # beginner | intermediate | advanced
    description: str = ""
    expected_outcome: str = ""
    estimated_minutes: int = 30


class KnowledgeCheck(BaseModel):
    """A verification question for knowledge assessment."""

    question: str
    expected_answer: str = ""
    topic: str = ""


class OnboardingChecklist(BaseModel):
    """Checklist for onboarding completion."""

    items: list[str] = Field(default_factory=list)
    estimated_duration: str = ""
    required_tools: list[str] = Field(default_factory=list)


class TrainingPlan(BaseModel):
    """Full training plan per section 10.6."""

    training_plan_id: str = Field(default_factory=generate_id)
    audience_role: str
    tool_scope: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    onboarding_steps: list[OnboardingStep] = Field(default_factory=list)
    exercises: list[Exercise] = Field(default_factory=list)
    knowledge_checks: list[KnowledgeCheck] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)


class FollowUpPlan(BaseModel):
    """Follow-up plan for adoption tracking."""

    user: str
    completion_status: str
    next_steps: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class UnresolvedIssue(BaseModel):
    """An issue to be routed as a work item."""

    issue: str
    suggested_owner: str = ""
    priority: str = "medium"


class TrainingEnablementInput(BaseModel):
    """Input data for the Training/Enablement Agent."""

    action: str  # onboarding_plan | setup_guide | faq | exercises | knowledge_checks | cheat_sheet | follow_up | route_issues
    audience_role: str | None = None
    tool_scope: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    topic: str | None = None
    common_issues: list[str] = Field(default_factory=list)
    skill_level: str = "beginner"
    user: str | None = None
    completion_status: str | None = None
    issues: list[str] = Field(default_factory=list)


class TrainingEnablementOutput(BaseModel):
    """Output of the Training/Enablement Agent."""

    action: str
    training_plan: TrainingPlan | None = None
    onboarding_checklist: OnboardingChecklist | None = None
    document_content: str | None = None
    exercises: list[Exercise] = Field(default_factory=list)
    knowledge_checks: list[KnowledgeCheck] = Field(default_factory=list)
    follow_up_plan: FollowUpPlan | None = None
    routed_issues: list[UnresolvedIssue] = Field(default_factory=list)
