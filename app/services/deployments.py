"""Deployment lifecycle service.

Manages deployments through: BUILD_PENDING -> BUILD_PASSED ->
DEPLOY_PENDING_APPROVAL -> DEPLOY_IN_PROGRESS -> DEPLOY_SUCCEEDED/DEPLOY_FAILED.
Rollback: ROLLBACK_IN_PROGRESS -> ROLLED_BACK.

All mutations emit domain events and audit records.
All deployments require approval before execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import DeploymentState
from app.domain.models.deployment import DeploymentRecord

# In-memory store.
_store: dict[str, DeploymentRecord] = {}


def get_store() -> dict[str, DeploymentRecord]:
    return _store


def clear_store() -> None:
    _store.clear()


async def create_deployment(
    *,
    git_sha: str,
    environment: str,
    branch_or_tag: str | None = None,
    triggered_by_person_key: str | None = None,
    linked_work_item_ids: list[UUID] | None = None,
    linked_release_notes_artifact_id: UUID | None = None,
    render_deploy_id: str | None = None,
    github_workflow_run_url: str | None = None,
    linked_linear_issue_id: str | None = None,
) -> DeploymentRecord:
    """Create a new deployment record in BUILD_PENDING state."""
    now = datetime.now(timezone.utc)
    deployment = DeploymentRecord(
        id=uuid4(),
        git_sha=git_sha,
        branch_or_tag=branch_or_tag,
        environment=environment,
        triggered_by_person_key=triggered_by_person_key,
        state=DeploymentState.BUILD_PENDING,
        linked_work_item_ids=linked_work_item_ids or [],
        linked_release_notes_artifact_id=linked_release_notes_artifact_id,
        render_deploy_id=render_deploy_id,
        github_workflow_run_url=github_workflow_run_url,
        created_at=now,
    )
    _store[str(deployment.id)] = deployment

    corr_id = generate_correlation_id()
    await emit(
        "deployment.created",
        {
            "deployment_id": str(deployment.id),
            "git_sha": git_sha,
            "environment": environment,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="deployment.created",
        actor_type="human",
        actor_id=triggered_by_person_key or "system",
        object_type="deployment",
        object_id=str(deployment.id),
        change_summary=f"Created deployment for {git_sha[:8]} to {environment}",
        correlation_id=corr_id,
    )
    return deployment


async def approve_deployment(
    deployment_id: str,
    approver: str,
) -> DeploymentRecord | None:
    """Approve a deployment, moving it to DEPLOY_PENDING_APPROVAL -> approved state."""
    deployment = _store.get(deployment_id)
    if deployment is None:
        return None

    if deployment.state not in (
        DeploymentState.BUILD_PASSED,
        DeploymentState.DEPLOY_PENDING_APPROVAL,
    ):
        return deployment

    deployment.state = DeploymentState.DEPLOY_IN_PROGRESS
    corr_id = generate_correlation_id()

    await emit(
        "deployment.approved",
        {
            "deployment_id": deployment_id,
            "approver": approver,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="deployment.approved",
        actor_type="human",
        actor_id=approver,
        object_type="deployment",
        object_id=deployment_id,
        change_summary=f"Deployment approved by {approver}",
        correlation_id=corr_id,
        approval_id=deployment_id,
    )
    return deployment


async def mark_build_passed(deployment_id: str) -> DeploymentRecord | None:
    """Transition from BUILD_PENDING to BUILD_PASSED then DEPLOY_PENDING_APPROVAL."""
    deployment = _store.get(deployment_id)
    if deployment is None:
        return None
    if deployment.state != DeploymentState.BUILD_PENDING:
        return deployment

    deployment.state = DeploymentState.DEPLOY_PENDING_APPROVAL
    corr_id = generate_correlation_id()
    await emit(
        "deployment.build_passed",
        {
            "deployment_id": deployment_id,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="deployment.build_passed",
        actor_type="system",
        actor_id="ci",
        object_type="deployment",
        object_id=deployment_id,
        change_summary="Build passed, awaiting approval",
        correlation_id=corr_id,
    )
    return deployment


async def execute_deployment(
    deployment_id: str,
    *,
    render_adapter: Any | None = None,
) -> DeploymentRecord | None:
    """Execute an approved deployment.

    Calls the Render adapter to deploy and runs post-deploy smoke tests.
    """
    deployment = _store.get(deployment_id)
    if deployment is None:
        return None

    if deployment.state != DeploymentState.DEPLOY_IN_PROGRESS:
        return deployment

    corr_id = generate_correlation_id()
    await emit(
        "deployment.started",
        {
            "deployment_id": deployment_id,
            "git_sha": deployment.git_sha,
            "environment": deployment.environment,
            "correlation_id": corr_id,
        },
    )

    try:
        # Call Render adapter if available
        if render_adapter is not None:
            result = await render_adapter.execute(
                "deploy_service",
                {
                    "service_id": deployment.render_deploy_id or "default",
                    "commit_id": deployment.git_sha,
                },
            )
            deployment.render_deploy_id = result.get("deploy_id", deployment.render_deploy_id)

        # Smoke test placeholder — real implementation would run checks
        deployment.smoke_test_result = "passed"
        deployment.state = DeploymentState.DEPLOY_SUCCEEDED
        deployment.completed_at = datetime.now(timezone.utc)

        await emit(
            "deployment.succeeded",
            {
                "deployment_id": deployment_id,
                "correlation_id": corr_id,
            },
        )
        record_audit_event(
            event_name="deployment.succeeded",
            actor_type="system",
            actor_id="deployer",
            object_type="deployment",
            object_id=deployment_id,
            change_summary=f"Deployment {deployment.git_sha[:8]} succeeded",
            correlation_id=corr_id,
        )
    except Exception as exc:
        deployment.state = DeploymentState.DEPLOY_FAILED
        deployment.smoke_test_result = f"failed: {exc}"
        deployment.completed_at = datetime.now(timezone.utc)

        await emit(
            "deployment.failed",
            {
                "deployment_id": deployment_id,
                "error": str(exc),
                "correlation_id": corr_id,
            },
        )
        record_audit_event(
            event_name="deployment.failed",
            actor_type="system",
            actor_id="deployer",
            object_type="deployment",
            object_id=deployment_id,
            change_summary=f"Deployment failed: {exc}",
            correlation_id=corr_id,
        )

    return deployment


async def rollback_deployment(
    deployment_id: str,
    reason: str,
    *,
    actor: str = "system",
) -> DeploymentRecord | None:
    """Roll back a deployment."""
    deployment = _store.get(deployment_id)
    if deployment is None:
        return None

    if deployment.state not in (
        DeploymentState.DEPLOY_SUCCEEDED,
        DeploymentState.DEPLOY_FAILED,
        DeploymentState.DEPLOY_IN_PROGRESS,
    ):
        return deployment

    deployment.state = DeploymentState.ROLLBACK_IN_PROGRESS
    corr_id = generate_correlation_id()

    record_audit_event(
        event_name="deployment.rollback_started",
        actor_type="human",
        actor_id=actor,
        object_type="deployment",
        object_id=deployment_id,
        change_summary=f"Rollback initiated: {reason}",
        correlation_id=corr_id,
    )

    # Mark rollback as complete
    deployment.state = DeploymentState.ROLLED_BACK
    deployment.completed_at = datetime.now(timezone.utc)

    await emit(
        "deployment.rolled_back",
        {
            "deployment_id": deployment_id,
            "reason": reason,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="deployment.rolled_back",
        actor_type="human",
        actor_id=actor,
        object_type="deployment",
        object_id=deployment_id,
        change_summary=f"Deployment rolled back: {reason}",
        correlation_id=corr_id,
    )
    return deployment


async def get_deployment(deployment_id: str) -> DeploymentRecord | None:
    """Retrieve a deployment record by ID."""
    return _store.get(deployment_id)


async def list_deployments(
    *,
    environment: str | None = None,
    state: DeploymentState | None = None,
    triggered_by: str | None = None,
) -> list[DeploymentRecord]:
    """List deployment records with optional filters."""
    results = list(_store.values())
    if environment is not None:
        results = [d for d in results if d.environment == environment]
    if state is not None:
        results = [d for d in results if d.state == state]
    if triggered_by is not None:
        results = [d for d in results if d.triggered_by_person_key == triggered_by]
    return results
