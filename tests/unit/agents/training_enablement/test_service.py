"""Tests for app.agents.training_enablement.service — TrainingEnablementAgent."""
from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult
from app.agents.training_enablement.schemas import (
    Exercise,
    KnowledgeCheck,
    OnboardingChecklist,
    TrainingEnablementOutput,
    TrainingPlan,
)
from app.agents.training_enablement.service import TrainingEnablementAgent


@pytest.fixture
def agent() -> TrainingEnablementAgent:
    return TrainingEnablementAgent()


@pytest.fixture
def context_factory():
    def _make(input_data: dict) -> AgentContext:
        return AgentContext(
            correlation_id="corr-test",
            work_item_id="wi-789",
            input_data=input_data,
        )
    return _make


# ---------------------------------------------------------------------------
# Onboarding plan generation per role
# ---------------------------------------------------------------------------

class TestOnboardingPlan:
    @pytest.mark.asyncio
    async def test_data_analyst_onboarding(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "data_analyst",
            "tool_scope": ["snowflake", "looker"],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        plan = output.training_plan
        assert plan is not None
        assert plan.audience_role == "data_analyst"
        assert "snowflake" in plan.tool_scope
        assert len(plan.learning_objectives) > 0
        assert len(plan.onboarding_steps) > 0

    @pytest.mark.asyncio
    async def test_data_engineer_onboarding(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "data_engineer",
            "tool_scope": ["dbt", "airflow"],
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        plan = output.training_plan
        assert plan.audience_role == "data_engineer"
        # Should have role-specific objectives
        assert any("dbt" in obj.lower() for obj in plan.learning_objectives)

    @pytest.mark.asyncio
    async def test_generic_role_onboarding(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "business_user",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert output.training_plan is not None
        assert output.training_plan.audience_role == "business_user"

    @pytest.mark.asyncio
    async def test_onboarding_includes_checklist(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "data_analyst",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        checklist = output.onboarding_checklist
        assert checklist is not None
        assert len(checklist.items) > 0
        assert len(checklist.estimated_duration) > 0


# ---------------------------------------------------------------------------
# Setup guide generation
# ---------------------------------------------------------------------------

class TestSetupGuide:
    @pytest.mark.asyncio
    async def test_setup_guide_for_tool(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "setup_guide",
            "tool_name": "Snowflake",
            "prerequisites": ["VPN access", "SSO credentials"],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert output.document_content is not None
        assert "Snowflake" in output.document_content
        assert "VPN access" in output.document_content

    @pytest.mark.asyncio
    async def test_setup_guide_without_prerequisites(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "setup_guide",
            "tool_name": "dbt",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert "dbt" in output.document_content


# ---------------------------------------------------------------------------
# FAQ generation
# ---------------------------------------------------------------------------

class TestFAQ:
    @pytest.mark.asyncio
    async def test_faq_with_issues(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "faq",
            "topic": "Snowflake",
            "common_issues": ["Connection timeout", "Permission denied"],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert "Snowflake" in output.document_content
        assert "Connection timeout" in output.document_content
        assert "Permission denied" in output.document_content

    @pytest.mark.asyncio
    async def test_faq_without_issues_has_default(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "faq", "topic": "Airflow"})
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert "Airflow" in output.document_content


# ---------------------------------------------------------------------------
# Exercise generation
# ---------------------------------------------------------------------------

class TestExercises:
    @pytest.mark.asyncio
    async def test_beginner_exercises(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "exercises",
            "tool_name": "dbt",
            "skill_level": "beginner",
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert len(output.exercises) >= 1
        assert all(isinstance(e, Exercise) for e in output.exercises)
        assert output.exercises[0].skill_level == "beginner"

    @pytest.mark.asyncio
    async def test_advanced_exercises_include_all_levels(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "exercises",
            "tool_name": "dbt",
            "skill_level": "advanced",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        levels = {e.skill_level for e in output.exercises}
        assert "beginner" in levels
        assert "intermediate" in levels
        assert "advanced" in levels

    @pytest.mark.asyncio
    async def test_exercises_have_expected_outcome(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "exercises",
            "tool_name": "Looker",
            "skill_level": "beginner",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        for exercise in output.exercises:
            assert len(exercise.expected_outcome) > 0


# ---------------------------------------------------------------------------
# Knowledge checks
# ---------------------------------------------------------------------------

class TestKnowledgeChecks:
    @pytest.mark.asyncio
    async def test_knowledge_checks_generated(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "knowledge_checks", "topic": "Data Governance"})
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert len(output.knowledge_checks) > 0
        assert all(isinstance(kc, KnowledgeCheck) for kc in output.knowledge_checks)

    @pytest.mark.asyncio
    async def test_knowledge_checks_have_answers(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "knowledge_checks", "topic": "SQL"})
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        for kc in output.knowledge_checks:
            assert len(kc.expected_answer) > 0


# ---------------------------------------------------------------------------
# Completion criteria
# ---------------------------------------------------------------------------

class TestCompletionCriteria:
    @pytest.mark.asyncio
    async def test_onboarding_has_completion_criteria(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "data_analyst",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert len(output.training_plan.completion_criteria) > 0


# ---------------------------------------------------------------------------
# Follow-up plan
# ---------------------------------------------------------------------------

class TestFollowUpPlan:
    @pytest.mark.asyncio
    async def test_follow_up_complete(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "follow_up",
            "user": "payas",
            "completion_status": "complete",
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert output.follow_up_plan is not None
        assert output.follow_up_plan.user == "payas"
        assert output.follow_up_plan.completion_status == "complete"
        assert len(output.follow_up_plan.next_steps) > 0

    @pytest.mark.asyncio
    async def test_follow_up_partial(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "follow_up",
            "user": "alice",
            "completion_status": "partial",
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert len(output.follow_up_plan.unresolved_issues) > 0


# ---------------------------------------------------------------------------
# Output matches TrainingPlan schema
# ---------------------------------------------------------------------------

class TestTrainingPlanSchema:
    @pytest.mark.asyncio
    async def test_training_plan_validates(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "onboarding_plan",
            "audience_role": "data_scientist",
            "tool_scope": ["mlflow", "jupyter"],
        })
        result = await agent.execute(ctx)
        output = TrainingEnablementOutput.model_validate(result.outputs)
        plan = output.training_plan
        assert isinstance(plan.training_plan_id, str)
        assert len(plan.training_plan_id) > 0
        assert isinstance(plan.audience_role, str)
        assert isinstance(plan.tool_scope, list)
        assert isinstance(plan.learning_objectives, list)
        assert isinstance(plan.prerequisites, list)
        assert isinstance(plan.onboarding_steps, list)
        assert isinstance(plan.exercises, list)
        assert isinstance(plan.knowledge_checks, list)
        assert isinstance(plan.artifacts, list)
        assert isinstance(plan.completion_criteria, list)
        assert isinstance(plan.follow_up_actions, list)


# ---------------------------------------------------------------------------
# Route unresolved issues
# ---------------------------------------------------------------------------

class TestRouteIssues:
    @pytest.mark.asyncio
    async def test_route_issues(self, agent, context_factory) -> None:
        ctx = context_factory({
            "action": "route_issues",
            "issues": ["Cannot access Snowflake", "VPN not working"],
        })
        result = await agent.execute(ctx)
        assert result.status == "success"
        output = TrainingEnablementOutput.model_validate(result.outputs)
        assert len(output.routed_issues) == 2


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------

class TestTrainingAgentMeta:
    def test_name(self) -> None:
        assert TrainingEnablementAgent().name == "training_enablement_agent"

    def test_required_inputs(self) -> None:
        assert "action" in TrainingEnablementAgent().required_inputs

    def test_handoff_targets(self) -> None:
        agent = TrainingEnablementAgent()
        assert "data_pm" in agent.get_handoff_targets()

    @pytest.mark.asyncio
    async def test_missing_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({})
        result = await agent.execute(ctx)
        assert result.status == "failure"

    @pytest.mark.asyncio
    async def test_invalid_action_fails(self, agent, context_factory) -> None:
        ctx = context_factory({"action": "nonexistent"})
        result = await agent.execute(ctx)
        assert result.status == "failure"
