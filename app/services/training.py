"""Training service — routes training plan generation through the Training/Enablement Agent.

Registers output as a versioned artifact and emits domain events.
"""
from __future__ import annotations

import json

from app.agents.base import AgentContext
from app.agents.training_enablement.service import TrainingEnablementAgent
from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id, generate_id
from app.domain.enums import ArtifactType
from app.domain.models.artifact import Artifact
from app.services.artifacts import register_artifact


async def generate_training_plan(
    *,
    role: str,
    tool_scope: list[str] | None = None,
    user: str | None = None,
    project_id: str | None = None,
    work_item_id: str | None = None,
) -> Artifact:
    """Generate a training plan via the Training/Enablement Agent and register as artifact.

    Parameters
    ----------
    role:
        The audience role for the training plan (e.g. data_analyst, data_engineer).
    tool_scope:
        List of tools the training plan should cover.
    user:
        The user the training plan is being generated for.
    project_id:
        Optional project ID to link the artifact to.
    work_item_id:
        Optional work item ID to link the artifact to.

    Returns
    -------
    Artifact registered in the artifact store.
    """
    correlation_id = generate_correlation_id()

    agent_input = {
        "action": "onboarding_plan",
        "audience_role": role,
        "tool_scope": tool_scope or [],
    }

    agent = TrainingEnablementAgent()
    agent_context = AgentContext(
        correlation_id=correlation_id,
        work_item_id=work_item_id,
        project_id=project_id,
        input_data=agent_input,
    )

    result = await agent.execute(agent_context)

    if result.status != "success":
        raise RuntimeError(
            f"Training plan generation failed: {result.errors}"
        )

    content = json.dumps(result.outputs, indent=2, default=str)

    artifact = await register_artifact(
        artifact_type=ArtifactType.TRAINING_PLAN,
        version="1.0",
        storage_uri=f"omdt://training/{generate_id()}",
        content=content,
        linked_object_type="work_item" if work_item_id else "project" if project_id else None,
        linked_object_id=work_item_id or project_id,
        created_by="training_enablement_agent",
    )

    await emit(
        "training.plan_generated",
        {
            "artifact_id": artifact.id,
            "role": role,
            "tool_scope": tool_scope or [],
            "user": user,
            "correlation_id": correlation_id,
            "work_item_id": work_item_id,
            "project_id": project_id,
        },
    )

    record_audit_event(
        event_name="training.plan_generated",
        actor_type="agent",
        actor_id="training_enablement_agent",
        object_type="artifact",
        object_id=artifact.id,
        change_summary=f"Generated training plan for role: {role}",
        correlation_id=correlation_id,
    )

    return artifact
