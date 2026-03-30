"""Technical Writer Agent — generates documents, detects gaps, produces checklists."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.technical_writer.schemas import (
    DocumentOutput,
    MissingFact,
    ReviewChecklistItem,
    TechnicalWriterInput,
    TechnicalWriterOutput,
)


# ---------------------------------------------------------------------------
# Tone selection
# ---------------------------------------------------------------------------

_AUDIENCE_TONE: dict[str, str] = {
    "executive": "concise, high-level, business-oriented",
    "technical": "detailed, precise, implementation-focused",
    "operational": "step-by-step, procedural, action-oriented",
    "end_user": "friendly, clear, jargon-free",
}


def _tone_for_audience(audience: str) -> str:
    """Return the writing tone appropriate for the audience."""
    return _AUDIENCE_TONE.get(audience, _AUDIENCE_TONE["technical"])


# ---------------------------------------------------------------------------
# Document generators
# ---------------------------------------------------------------------------

def _generate_executive_summary(
    source_artifacts: list[str], audience: str, title: str | None
) -> DocumentOutput:
    tone = _tone_for_audience(audience)
    return DocumentOutput(
        document_type="executive_summary",
        audience=audience,
        title=title or "Executive Summary",
        executive_summary=(
            f"This executive summary synthesizes {len(source_artifacts)} source artifact(s). "
            f"Written in a {tone} tone for {audience} audience."
        ),
        source_artifacts=source_artifacts,
        key_changes_or_findings=["Key finding derived from source artifacts."],
        procedure_or_narrative="High-level overview of findings and recommendations.",
        risks_and_caveats=["Conclusions depend on completeness of source artifacts."],
        publication_targets=["email", "confluence"],
    )


def _generate_technical_memo(
    source_artifacts: list[str], audience: str, title: str | None
) -> DocumentOutput:
    tone = _tone_for_audience(audience)
    return DocumentOutput(
        document_type="technical_memo",
        audience=audience,
        title=title or "Technical Memo",
        executive_summary=f"Technical memo covering {len(source_artifacts)} artifact(s).",
        source_artifacts=source_artifacts,
        key_changes_or_findings=["Technical finding from analysis."],
        prerequisites=["Access to relevant systems and data sources."],
        procedure_or_narrative=(
            f"Detailed technical analysis written in a {tone} tone. "
            "Covers methodology, findings, and technical recommendations."
        ),
        risks_and_caveats=["Technical debt implications should be reviewed."],
        glossary={"artifact": "A versioned output registered in the OMDT artifact store"},
        publication_targets=["confluence", "github_wiki"],
    )


def _generate_runbook(
    source_artifacts: list[str], title: str | None
) -> DocumentOutput:
    return DocumentOutput(
        document_type="runbook",
        audience="operational",
        title=title or "Operational Runbook",
        executive_summary="Step-by-step operational procedures for the described process.",
        source_artifacts=source_artifacts,
        prerequisites=["System access credentials", "Monitoring dashboard access"],
        procedure_or_narrative=(
            "1. Verify system health\n"
            "2. Execute procedure steps\n"
            "3. Validate outcomes\n"
            "4. Document results and escalate if needed"
        ),
        risks_and_caveats=["Ensure rollback plan is available before executing."],
        publication_targets=["runbook_repo"],
    )


def _generate_release_notes(
    deployment_record: dict | None, changes: list[str], title: str | None
) -> DocumentOutput:
    version = (deployment_record or {}).get("version", "N/A")
    environment = (deployment_record or {}).get("environment", "N/A")
    change_items = changes if changes else ["No changes listed."]
    return DocumentOutput(
        document_type="release_notes",
        audience="technical",
        title=title or f"Release Notes — {version}",
        executive_summary=f"Release {version} deployed to {environment}.",
        key_changes_or_findings=change_items,
        procedure_or_narrative=(
            f"Version {version} has been deployed to {environment}. "
            f"This release includes {len(change_items)} change(s)."
        ),
        risks_and_caveats=["Monitor post-deployment metrics for anomalies."],
        publication_targets=["email", "slack"],
    )


def _generate_sop(
    process_description: str | None, title: str | None
) -> DocumentOutput:
    desc = process_description or "Process description not provided."
    return DocumentOutput(
        document_type="sop",
        audience="operational",
        title=title or "Standard Operating Procedure",
        executive_summary=f"SOP for: {desc[:100]}",
        prerequisites=["Relevant system access", "Completed training"],
        procedure_or_narrative=desc,
        risks_and_caveats=["Deviations from SOP must be documented and approved."],
        publication_targets=["sop_repo"],
    )


def _generate_user_guide(
    feature: str | None, audience: str, title: str | None
) -> DocumentOutput:
    feat = feature or "the described feature"
    tone = _tone_for_audience(audience)
    return DocumentOutput(
        document_type="user_guide",
        audience=audience,
        title=title or f"User Guide: {feat}",
        executive_summary=f"Guide for using {feat}.",
        prerequisites=["Account access", "Basic familiarity with the platform"],
        procedure_or_narrative=(
            f"Step-by-step guide for {feat}, written in a {tone} tone. "
            "Covers setup, usage, and troubleshooting."
        ),
        risks_and_caveats=["Feature behavior may change in future releases."],
        publication_targets=["docs_site"],
    )


# ---------------------------------------------------------------------------
# Gap detection and review checklist
# ---------------------------------------------------------------------------

_EXPECTED_FIELDS = [
    "title", "audience", "source_artifacts", "procedure_or_narrative",
]


def _detect_missing_facts(source_artifacts: list[str]) -> list[MissingFact]:
    """Identify gaps in source material that need clarification."""
    missing: list[MissingFact] = []
    if not source_artifacts:
        missing.append(MissingFact(
            field="source_artifacts",
            question="No source artifacts provided. What source material should be used?",
        ))
    else:
        # Check for completeness signals
        missing.append(MissingFact(
            field="context",
            question="Is additional context available beyond the listed source artifacts?",
            source_artifact=source_artifacts[0] if source_artifacts else None,
        ))
    return missing


def _generate_review_checklist(document: dict | None) -> list[ReviewChecklistItem]:
    """Generate a review checklist for a document."""
    items = [
        ReviewChecklistItem(item="Title is clear and descriptive"),
        ReviewChecklistItem(item="Executive summary is present and accurate"),
        ReviewChecklistItem(item="Source artifacts are cited"),
        ReviewChecklistItem(item="Audience-appropriate tone is used"),
        ReviewChecklistItem(item="Prerequisites are listed if applicable"),
        ReviewChecklistItem(item="Risks and caveats are documented"),
        ReviewChecklistItem(item="Glossary covers domain-specific terms"),
        ReviewChecklistItem(item="Publication targets are specified"),
    ]
    if document:
        # Mark items as checked if the document has those fields populated
        doc_keys = set(document.keys())
        for item in items:
            if "title" in item.item.lower() and document.get("title"):
                item.checked = True
            elif "executive summary" in item.item.lower() and document.get("executive_summary"):
                item.checked = True
            elif "source artifact" in item.item.lower() and document.get("source_artifacts"):
                item.checked = True
    return items


# ---------------------------------------------------------------------------
# Technical Writer Agent
# ---------------------------------------------------------------------------

_VALID_ACTIONS = {
    "executive_summary",
    "technical_memo",
    "runbook",
    "release_notes",
    "sop",
    "user_guide",
    "detect_missing",
    "review_checklist",
}


class TechnicalWriterAgent(BaseAgent):
    """Generates technical documents, detects gaps, and produces review checklists.

    Implements the technical writer role from PRD section 10.5.
    """

    name = "technical_writer_agent"
    mission = (
        "Generate executive summaries, technical memos, runbooks, release "
        "notes, SOPs, and user guides from source artifacts. Detect missing "
        "facts and request clarification instead of assuming. Produce "
        "review checklists for document quality."
    )
    allowed_tools = [
        "read_artifact",
        "create_document",
        "update_document",
        "attach_artifact",
        "request_clarification",
        "publish_document",
        "create_review_task",
    ]
    required_inputs = ["action"]
    output_schema = TechnicalWriterOutput
    handoff_targets = ["data_pm", "head_of_data"]

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate the requested document or analysis."""
        inputs = context.input_data

        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        writer_input = TechnicalWriterInput.model_validate(inputs)
        action = writer_input.action

        if action not in _VALID_ACTIONS:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Unknown action: {action}. Valid: {sorted(_VALID_ACTIONS)}"],
            )

        output = TechnicalWriterOutput(action=action)

        if action == "executive_summary":
            output.document = _generate_executive_summary(
                writer_input.source_artifacts, writer_input.audience, writer_input.title
            )

        elif action == "technical_memo":
            output.document = _generate_technical_memo(
                writer_input.source_artifacts, writer_input.audience, writer_input.title
            )

        elif action == "runbook":
            output.document = _generate_runbook(
                writer_input.source_artifacts, writer_input.title
            )

        elif action == "release_notes":
            output.document = _generate_release_notes(
                writer_input.deployment_record, writer_input.changes, writer_input.title
            )

        elif action == "sop":
            output.document = _generate_sop(
                writer_input.process_description, writer_input.title
            )

        elif action == "user_guide":
            output.document = _generate_user_guide(
                writer_input.feature, writer_input.audience, writer_input.title
            )

        elif action == "detect_missing":
            output.missing_facts = _detect_missing_facts(writer_input.source_artifacts)

        elif action == "review_checklist":
            output.review_checklist = _generate_review_checklist(writer_input.document)

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
