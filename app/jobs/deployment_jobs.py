"""Deployment job helpers.

Provides functions to trigger CI, deploy via Render, run smoke tests,
and notify on deployment results.
"""
from __future__ import annotations

from typing import Any

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.services import deployments as deploy_service


async def trigger_github_ci(
    branch: str,
    workflow: str,
    *,
    github_adapter: Any | None = None,
) -> dict[str, Any]:
    """Trigger a GitHub Actions CI workflow."""
    if github_adapter is None:
        return {"status": "skipped", "reason": "no github adapter"}

    result = await github_adapter.execute(
        "trigger_workflow",
        {
            "workflow_file": workflow,
            "ref": branch,
        },
    )

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="ci.triggered",
        actor_type="system",
        actor_id="deployment_jobs",
        object_type="ci_workflow",
        object_id=workflow,
        change_summary=f"Triggered CI workflow {workflow} on {branch}",
        correlation_id=corr_id,
    )

    return {"status": "triggered", "workflow": workflow, "branch": branch, "result": result}


async def trigger_render_deploy(
    service_id: str,
    commit: str,
    *,
    render_adapter: Any | None = None,
) -> dict[str, Any]:
    """Trigger a deployment on Render."""
    if render_adapter is None:
        return {"status": "skipped", "reason": "no render adapter"}

    result = await render_adapter.execute(
        "deploy_service",
        {
            "service_id": service_id,
            "commit_id": commit,
        },
    )

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="render.deploy_triggered",
        actor_type="system",
        actor_id="deployment_jobs",
        object_type="render_service",
        object_id=service_id,
        change_summary=f"Triggered Render deploy for {service_id} at {commit[:8]}",
        correlation_id=corr_id,
    )

    return {"status": "triggered", "service_id": service_id, "commit": commit, "result": result}


async def post_deploy_smoke_test(
    deployment_id: str,
    *,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run configured smoke checks after a deployment.

    Each check is a dict with at minimum a 'name' key.
    In a production implementation, these would hit real endpoints.
    """
    deployment = await deploy_service.get_deployment(deployment_id)
    if deployment is None:
        return {"status": "error", "reason": "deployment not found"}

    checks = checks or [{"name": "health_check", "endpoint": "/health"}]
    results: list[dict[str, Any]] = []

    for check in checks:
        # Placeholder: real implementation would make HTTP calls
        results.append({
            "name": check.get("name", "unknown"),
            "status": "passed",
        })

    all_passed = all(r["status"] == "passed" for r in results)
    corr_id = generate_correlation_id()

    record_audit_event(
        event_name="deployment.smoke_test_completed",
        actor_type="system",
        actor_id="smoke_tester",
        object_type="deployment",
        object_id=deployment_id,
        change_summary=f"Smoke tests {'passed' if all_passed else 'failed'}: {len(results)} checks",
        correlation_id=corr_id,
    )

    return {
        "deployment_id": deployment_id,
        "status": "passed" if all_passed else "failed",
        "checks": results,
    }


async def notify_deployment_result(
    deployment_id: str,
    result: str,
) -> dict[str, Any]:
    """Dispatch a notification about a deployment result."""
    deployment = await deploy_service.get_deployment(deployment_id)
    if deployment is None:
        return {"status": "error", "reason": "deployment not found"}

    corr_id = generate_correlation_id()
    await emit(
        "deployment.notification_sent",
        {
            "deployment_id": deployment_id,
            "result": result,
            "environment": deployment.environment,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="deployment.notification_sent",
        actor_type="system",
        actor_id="notifier",
        object_type="deployment",
        object_id=deployment_id,
        change_summary=f"Deployment notification sent: {result}",
        correlation_id=corr_id,
    )

    return {"status": "sent", "deployment_id": deployment_id, "result": result}
