"""Workflow E2E test: research lifecycle.

REQUESTED -> SCOPED -> PAPER_COLLECTION -> SUMMARY_DRAFTED -> REVIEWED -> PUBLISHED -> CLOSED

Since the canonical state machine doesn't have research-specific states,
we model this as a work item progressing through the standard states with
research-specific agent actions at each step.
"""
from __future__ import annotations

import pytest

from app.agents.academic.schemas import AcademicResearchOutput
from app.agents.academic.service import AcademicResearchAgent
from app.agents.base import AgentContext
from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import ArtifactType, CanonicalState
from app.services import artifacts, work_items
from app.services.work_items import transition_work_item
from app.workflows.engine import WorkflowEngine


SAMPLE_PAPERS = [
    {"paper_id": "p1", "title": "Paper One", "method": "method_a", "dataset": "ds1", "metrics": ["F1"]},
    {"paper_id": "p2", "title": "Paper Two", "method": "method_b", "dataset": "ds2", "metrics": ["Acc"]},
]


@pytest.fixture(autouse=True)
def _clean():
    work_items.clear_store()
    artifacts.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    work_items.clear_store()
    artifacts.clear_store()
    clear_audit_log()
    clear_handlers()


class TestResearchLifecycle:
    """Research lifecycle mapped to canonical states."""

    @pytest.mark.asyncio
    async def test_full_research_lifecycle(self) -> None:
        """Full research lifecycle: create -> scope -> collect -> summarize -> review -> publish -> close."""
        agent = AcademicResearchAgent()
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        # 1. REQUESTED (NEW) -> SCOPED (TRIAGE)
        wi = await work_items.create_work_item(title="Literature review: ML efficiency")
        r = await transition_work_item(wi.id, CanonicalState.TRIAGE, actor="researcher", engine=engine)
        assert r.success

        # 2. SCOPED -> PAPER_COLLECTION (READY_FOR_PRD)
        r = await transition_work_item(wi.id, CanonicalState.READY_FOR_PRD, actor="researcher", engine=engine)
        assert r.success

        # 3. Collect papers via agent
        ctx = AgentContext(
            correlation_id="corr-research",
            work_item_id=wi.id,
            input_data={"action": "parse_metadata", "source": "https://arxiv.org/abs/2001.00001"},
        )
        result = await agent.execute(ctx)
        assert result.status == "success"

        # 4. SUMMARY_DRAFTED (PRD_DRAFTING)
        r = await transition_work_item(wi.id, CanonicalState.PRD_DRAFTING, actor="agent", engine=engine)
        assert r.success

        # Summarize papers
        ctx = AgentContext(
            correlation_id="corr-research",
            work_item_id=wi.id,
            input_data={"action": "compare", "papers": SAMPLE_PAPERS},
        )
        compare_result = await agent.execute(ctx)
        assert compare_result.status == "success"

        # 5. REVIEWED (PRD_REVIEW)
        r = await transition_work_item(wi.id, CanonicalState.PRD_REVIEW, actor="researcher", engine=engine)
        assert r.success

        # 6. PUBLISHED (APPROVAL_PENDING -> APPROVED)
        r = await transition_work_item(wi.id, CanonicalState.APPROVAL_PENDING, actor="researcher", engine=engine)
        assert r.success
        r = await transition_work_item(wi.id, CanonicalState.APPROVED, actor="lead", engine=engine)
        assert r.success

        # Register artifact
        artifact = await artifacts.register_artifact(
            artifact_type=ArtifactType.RESEARCH_BRIEF,
            version="1.0",
            storage_uri=f"artifacts/research/{wi.id}/brief.json",
            content="Research brief content",
            linked_object_type="work_item",
            linked_object_id=wi.id,
        )
        assert artifact is not None

        # 7. CLOSED (advance to DONE)
        for state in [CanonicalState.READY_FOR_BUILD, CanonicalState.IN_PROGRESS,
                      CanonicalState.VALIDATION, CanonicalState.DEPLOYMENT_PENDING,
                      CanonicalState.DEPLOYED, CanonicalState.DONE]:
            r = await transition_work_item(wi.id, state, actor="system", engine=engine)
            assert r.success

        final = await work_items.get_work_item(wi.id)
        assert final.canonical_state == CanonicalState.DONE

    @pytest.mark.asyncio
    async def test_research_audit_trail(self) -> None:
        """Verify audit trail captures research workflow transitions."""
        wi = await work_items.create_work_item(title="Research audit test")
        engine = WorkflowEngine(approval_checker=lambda wi_id, f, t: True)

        for state in [CanonicalState.TRIAGE, CanonicalState.READY_FOR_PRD,
                      CanonicalState.PRD_DRAFTING, CanonicalState.PRD_REVIEW]:
            await transition_work_item(wi.id, state, actor="researcher", engine=engine)

        audit = get_audit_log()
        state_changes = [r for r in audit if r["event_name"] == "work_item.state_changed"]
        assert len(state_changes) >= 4
