"""Integration test: paper review -> academic agent -> summary -> literature matrix -> artifact."""
from __future__ import annotations

import pytest

from app.agents.academic.schemas import AcademicResearchOutput
from app.agents.academic.service import AcademicResearchAgent
from app.agents.base import AgentContext
from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.domain.enums import ArtifactType
from app.services import artifacts, work_items


SAMPLE_PAPERS = [
    {
        "paper_id": "paper-001",
        "title": "Transformer Architecture for NLP",
        "authors": ["Author A"],
        "year": 2020,
        "method": "attention mechanism",
        "dataset": "WMT",
        "metrics": ["BLEU"],
        "main_results": "SOTA on translation",
        "limitations": ["compute cost"],
    },
    {
        "paper_id": "paper-002",
        "title": "Efficient Fine-Tuning Methods",
        "authors": ["Author B"],
        "year": 2022,
        "method": "LoRA",
        "dataset": "GLUE",
        "metrics": ["F1", "Accuracy"],
        "main_results": "Comparable to full fine-tuning",
        "limitations": ["limited to specific architectures"],
    },
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


class TestResearchPipeline:
    """Paper review request -> academic agent -> summary -> literature matrix -> artifact registered."""

    @pytest.mark.asyncio
    async def test_paper_summary_produces_output(self) -> None:
        """Academic agent summarizes a paper and produces structured output."""
        agent = AcademicResearchAgent()
        ctx = AgentContext(
            correlation_id="corr-research-001",
            work_item_id="wi-research",
            input_data={"action": "summarize", "papers": [SAMPLE_PAPERS[0]]},
        )
        result = await agent.execute(ctx)
        assert result.status == "success"

        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.paper_summary is not None
        assert output.paper_summary.title == "Transformer Architecture for NLP"

    @pytest.mark.asyncio
    async def test_literature_matrix_from_multiple_papers(self) -> None:
        """Academic agent generates a literature matrix from multiple papers."""
        agent = AcademicResearchAgent()
        ctx = AgentContext(
            correlation_id="corr-research-002",
            input_data={"action": "compare", "papers": SAMPLE_PAPERS},
        )
        result = await agent.execute(ctx)
        assert result.status == "success"

        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.literature_matrix is not None
        assert len(output.literature_matrix.papers) == 2
        assert "paper-001" in output.literature_matrix.matrix_data
        assert "paper-002" in output.literature_matrix.matrix_data

    @pytest.mark.asyncio
    async def test_research_artifact_registration(self) -> None:
        """Register a research brief as an artifact."""
        agent = AcademicResearchAgent()
        ctx = AgentContext(
            correlation_id="corr-research-003",
            input_data={"action": "executive_summary", "papers": SAMPLE_PAPERS},
        )
        result = await agent.execute(ctx)
        output = AcademicResearchOutput.model_validate(result.outputs)

        # Register the research brief as an artifact
        artifact = await artifacts.register_artifact(
            artifact_type=ArtifactType.RESEARCH_BRIEF,
            version="1.0",
            storage_uri="artifacts/research/brief-001.json",
            content=output.research_brief.synthesis,
            linked_object_type="work_item",
            linked_object_id="wi-research",
            created_by="academic_agent",
        )

        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.RESEARCH_BRIEF
        assert artifact.hash_sha256 != "0" * 64

    @pytest.mark.asyncio
    async def test_full_research_pipeline(self) -> None:
        """End-to-end: create work item -> summarize -> compare -> register artifact."""
        # 1. Create a work item for the research request
        wi = await work_items.create_work_item(
            title="Review transformers literature",
        )

        # 2. Summarize individual papers
        agent = AcademicResearchAgent()
        for paper in SAMPLE_PAPERS:
            ctx = AgentContext(
                correlation_id="corr-pipeline",
                work_item_id=wi.id,
                input_data={"action": "summarize", "papers": [paper]},
            )
            result = await agent.execute(ctx)
            assert result.status == "success"

        # 3. Generate literature matrix
        ctx = AgentContext(
            correlation_id="corr-pipeline",
            work_item_id=wi.id,
            input_data={"action": "compare", "papers": SAMPLE_PAPERS},
        )
        matrix_result = await agent.execute(ctx)
        assert matrix_result.status == "success"

        # 4. Register literature matrix as artifact
        artifact = await artifacts.register_artifact(
            artifact_type=ArtifactType.LITERATURE_MATRIX,
            version="1.0",
            storage_uri=f"artifacts/research/{wi.id}/matrix.json",
            content=str(matrix_result.outputs),
            linked_object_type="work_item",
            linked_object_id=wi.id,
            created_by="academic_research_agent",
        )

        assert artifact.linked_object_id == wi.id
        assert artifact.artifact_type == ArtifactType.LITERATURE_MATRIX

    @pytest.mark.asyncio
    async def test_handoff_to_downstream_agent(self) -> None:
        """Academic agent can hand off findings to a downstream agent."""
        agent = AcademicResearchAgent()
        ctx = AgentContext(
            correlation_id="corr-handoff",
            input_data={
                "action": "hand_off",
                "papers": SAMPLE_PAPERS,
                "target_agent": "data_scientist",
            },
        )
        result = await agent.execute(ctx)
        assert result.status == "success"

        output = AcademicResearchOutput.model_validate(result.outputs)
        assert output.handoff is not None
        assert output.handoff.target_agent == "data_scientist"
        assert len(output.handoff.source_paper_ids) == 2
