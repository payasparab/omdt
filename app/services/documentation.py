"""Documentation service — routes document generation through the Technical Writer Agent.

Registers output as a versioned artifact and emits domain events.
"""
from __future__ import annotations

import json

from app.agents.base import AgentContext
from app.agents.technical_writer.service import TechnicalWriterAgent
from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id, generate_id
from app.domain.enums import ArtifactType
from app.domain.models.artifact import Artifact
from app.services.artifacts import register_artifact

# Map document types to artifact types
_DOC_TYPE_TO_ARTIFACT: dict[str, ArtifactType] = {
    "executive_summary": ArtifactType.RESEARCH_BRIEF,
    "technical_memo": ArtifactType.TECHNICAL_MEMO,
    "runbook": ArtifactType.RUNBOOK,
    "release_notes": ArtifactType.RELEASE_NOTES,
    "sop": ArtifactType.SOP,
    "user_guide": ArtifactType.USER_GUIDE,
}


async def generate_document(
    *,
    document_type: str,
    source_artifacts: list[str] | None = None,
    audience: str = "technical",
    context: dict | None = None,
    project_id: str | None = None,
    work_item_id: str | None = None,
) -> Artifact:
    """Generate a document via the Technical Writer Agent and register as artifact.

    Parameters
    ----------
    document_type:
        One of: executive_summary, technical_memo, runbook, release_notes, sop, user_guide
    source_artifacts:
        List of artifact IDs to use as source material.
    audience:
        Target audience (executive, technical, operational, end_user).
    context:
        Additional context dict (deployment_record, changes, process_description, feature).
    project_id:
        Optional project ID to link the artifact to.
    work_item_id:
        Optional work item ID to link the artifact to.

    Returns
    -------
    Artifact registered in the artifact store.
    """
    correlation_id = generate_correlation_id()
    ctx_data = context or {}

    # Build agent input
    agent_input = {
        "action": document_type,
        "source_artifacts": source_artifacts or [],
        "audience": audience,
        **ctx_data,
    }

    agent = TechnicalWriterAgent()
    agent_context = AgentContext(
        correlation_id=correlation_id,
        work_item_id=work_item_id,
        project_id=project_id,
        input_data=agent_input,
    )

    result = await agent.execute(agent_context)

    if result.status != "success":
        raise RuntimeError(
            f"Document generation failed: {result.errors}"
        )

    # Serialize output as artifact content
    content = json.dumps(result.outputs, indent=2, default=str)
    artifact_type = _DOC_TYPE_TO_ARTIFACT.get(document_type, ArtifactType.TECHNICAL_MEMO)

    artifact = await register_artifact(
        artifact_type=artifact_type,
        version="1.0",
        storage_uri=f"omdt://documents/{generate_id()}",
        content=content,
        linked_object_type="work_item" if work_item_id else "project" if project_id else None,
        linked_object_id=work_item_id or project_id,
        created_by="technical_writer_agent",
    )

    await emit(
        "documentation.generated",
        {
            "artifact_id": artifact.id,
            "document_type": document_type,
            "audience": audience,
            "correlation_id": correlation_id,
            "work_item_id": work_item_id,
            "project_id": project_id,
        },
    )

    record_audit_event(
        event_name="documentation.generated",
        actor_type="agent",
        actor_id="technical_writer_agent",
        object_type="artifact",
        object_id=artifact.id,
        change_summary=f"Generated {document_type} document for audience: {audience}",
        correlation_id=correlation_id,
    )

    return artifact
