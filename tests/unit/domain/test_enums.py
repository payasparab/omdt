"""Tests for domain enumerations."""
from app.domain.enums import (
    AccessRequestState,
    ActorType,
    ApprovalStatus,
    ArtifactType,
    CanonicalState,
    DeploymentState,
    PipelineType,
    Priority,
    SourceChannel,
    WorkItemType,
)


class TestCanonicalState:
    def test_all_states_exist(self) -> None:
        expected = {
            "new", "triage", "needs_clarification", "ready_for_prd",
            "prd_drafting", "prd_review", "approval_pending", "approved",
            "ready_for_build", "in_progress", "blocked", "validation",
            "deployment_pending", "deployed", "done", "archived",
        }
        assert {s.value for s in CanonicalState} == expected

    def test_string_conversion(self) -> None:
        assert str(CanonicalState.NEW) == "CanonicalState.NEW"
        assert CanonicalState.NEW.value == "new"

    def test_member_count(self) -> None:
        assert len(CanonicalState) == 16


class TestWorkItemType:
    def test_all_types_exist(self) -> None:
        expected = {
            "analysis_request", "dashboard_request", "pipeline_request",
            "data_model_request", "data_science_request", "paper_review_request",
            "documentation_request", "training_request", "access_request",
            "bug_or_incident", "vendor_or_procurement", "status_or_reporting",
            "unknown_needs_clarification",
            "task", "bug", "deployment", "pipeline", "incident",
        }
        assert {t.value for t in WorkItemType} == expected

    def test_member_count(self) -> None:
        assert len(WorkItemType) == 18


class TestPriority:
    def test_all_priorities(self) -> None:
        expected = {"critical", "high", "medium", "low", "none"}
        assert {p.value for p in Priority} == expected


class TestActorType:
    def test_all_actor_types(self) -> None:
        expected = {"human", "agent", "system"}
        assert {a.value for a in ActorType} == expected


class TestSourceChannel:
    def test_all_channels(self) -> None:
        expected = {"outlook", "linear", "notion", "cli", "api", "email"}
        assert {c.value for c in SourceChannel} == expected


class TestArtifactType:
    def test_all_artifact_types(self) -> None:
        expected = {
            "prd", "research_brief", "literature_matrix", "sql_bundle",
            "notebook", "dashboard_spec", "dbml", "architecture_diagram",
            "deployment_manifest", "email_package", "presentation",
            "audit_export", "runbook", "release_notes", "user_guide",
            "technical_memo", "sop", "training_plan", "onboarding_checklist",
        }
        assert {a.value for a in ArtifactType} == expected

    def test_member_count(self) -> None:
        assert len(ArtifactType) == 19


class TestApprovalStatus:
    def test_all_statuses(self) -> None:
        expected = {"pending", "approved", "rejected"}
        assert {s.value for s in ApprovalStatus} == expected


class TestDeploymentState:
    def test_all_states(self) -> None:
        expected = {
            "build_pending", "build_passed", "deploy_pending_approval",
            "deploy_in_progress", "deploy_succeeded", "deploy_failed",
            "rollback_in_progress", "rolled_back",
        }
        assert {s.value for s in DeploymentState} == expected

    def test_member_count(self) -> None:
        assert len(DeploymentState) == 8


class TestAccessRequestState:
    def test_all_states(self) -> None:
        expected = {
            "requested", "policy_check", "approval_pending",
            "approved", "provisioning", "verified", "closed",
        }
        assert {s.value for s in AccessRequestState} == expected

    def test_member_count(self) -> None:
        assert len(AccessRequestState) == 7


class TestPipelineType:
    def test_all_types(self) -> None:
        expected = {
            "sql_transformation", "python_batch", "data_ingestion",
            "metric_refresh", "model_scoring", "report_generation",
            "sync_reconciliation", "maintenance_cleanup",
        }
        assert {t.value for t in PipelineType} == expected

    def test_member_count(self) -> None:
        assert len(PipelineType) == 8
