"""Deployments API router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.domain.enums import DeploymentState
from app.schemas.api.deployments import (
    ApproveDeploymentRequest,
    CreateDeploymentRequest,
    DeploymentResponse,
    RollbackDeploymentRequest,
)
from app.services import deployments as deploy_service

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])


def _deploy_to_response(d) -> DeploymentResponse:  # noqa: ANN001
    return DeploymentResponse(
        id=str(d.id),
        git_sha=d.git_sha,
        branch_or_tag=d.branch_or_tag,
        environment=d.environment,
        triggered_by_person_key=d.triggered_by_person_key,
        state=d.state.value if hasattr(d.state, "value") else d.state,
        linked_work_item_ids=[str(i) for i in d.linked_work_item_ids],
        migration_result=d.migration_result,
        smoke_test_result=d.smoke_test_result,
        rollback_reference_id=str(d.rollback_reference_id) if d.rollback_reference_id else None,
        render_deploy_id=d.render_deploy_id,
        github_workflow_run_url=d.github_workflow_run_url,
        created_at=d.created_at,
        completed_at=d.completed_at,
    )


@router.post("", response_model=DeploymentResponse, status_code=201)
async def create_deployment(request: CreateDeploymentRequest) -> DeploymentResponse:
    """Create a new deployment record."""
    d = await deploy_service.create_deployment(
        git_sha=request.git_sha,
        environment=request.environment,
        branch_or_tag=request.branch_or_tag,
        triggered_by_person_key=request.triggered_by_person_key,
        linked_work_item_ids=[UUID(i) for i in request.linked_work_item_ids] if request.linked_work_item_ids else None,
        linked_release_notes_artifact_id=UUID(request.linked_release_notes_artifact_id) if request.linked_release_notes_artifact_id else None,
        render_deploy_id=request.render_deploy_id,
        github_workflow_run_url=request.github_workflow_run_url,
    )
    return _deploy_to_response(d)


@router.post("/{deployment_id}/approve", response_model=DeploymentResponse)
async def approve_deployment(
    deployment_id: str, request: ApproveDeploymentRequest
) -> DeploymentResponse:
    """Approve a deployment."""
    d = await deploy_service.approve_deployment(deployment_id, request.approver)
    if d is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _deploy_to_response(d)


@router.post("/{deployment_id}/execute", response_model=DeploymentResponse)
async def execute_deployment(deployment_id: str) -> DeploymentResponse:
    """Execute an approved deployment."""
    d = await deploy_service.execute_deployment(deployment_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _deploy_to_response(d)


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: str, request: RollbackDeploymentRequest
) -> DeploymentResponse:
    """Rollback a deployment."""
    d = await deploy_service.rollback_deployment(
        deployment_id, request.reason, actor=request.actor
    )
    if d is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _deploy_to_response(d)


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(deployment_id: str) -> DeploymentResponse:
    """Get a deployment record."""
    d = await deploy_service.get_deployment(deployment_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return _deploy_to_response(d)
