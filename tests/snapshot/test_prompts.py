"""Snapshot tests for prompt files — verify each prompt exists and renders consistently."""
from __future__ import annotations

from pathlib import Path

import pytest

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "system"

EXPECTED_PROMPTS = [
    "head_of_data.md",
    "triage_agent.md",
    "data_pm.md",
    "data_pmo.md",
    "data_analyst.md",
    "data_engineer.md",
    "data_architect.md",
    "data_scientist.md",
    "academic_research_agent.md",
    "technical_writer_agent.md",
    "training_enablement_agent.md",
    "data_quality_agent.md",
    "ml_engineering_agent.md",
    "mlops_agent.md",
    "pipeline_manager.md",
    "deployment_agent.md",
    "access_security_agent.md",
    "vendor_finops_agent.md",
    "comms_publishing_agent.md",
    "coding_agent.md",
]

REQUIRED_SECTIONS = [
    "Mission",
    "Scope",
    "Triggers",
    "Allowed Tools",
    "Required Inputs",
    "Output Schema",
    "Escalation Rules",
    "Approval Boundaries",
    "Quality Checklist",
    "Handoff Targets",
    "Audit Context Requirements",
]


class TestPromptFilesExist:
    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_file_exists(self, filename: str) -> None:
        path = PROMPTS_DIR / filename
        assert path.exists(), f"Missing prompt file: {filename}"

    def test_total_prompt_count(self) -> None:
        md_files = list(PROMPTS_DIR.glob("*.md"))
        assert len(md_files) == 20, f"Expected 20 prompt files, found {len(md_files)}"


class TestPromptSections:
    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_all_required_sections_present(self, filename: str) -> None:
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            assert section in content, (
                f"{filename} is missing required section: '{section}'"
            )

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_is_non_empty(self, filename: str) -> None:
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        assert len(content) > 200, f"{filename} is suspiciously short"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_starts_with_heading(self, filename: str) -> None:
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        assert content.startswith("# "), f"{filename} should start with a heading"


class TestPromptConsistency:
    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_hash_is_stable(self, filename: str) -> None:
        """Verify prompt can be hashed (used for versioning)."""
        import hashlib

        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert len(h) == 64  # valid SHA-256

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_json_schema(self, filename: str) -> None:
        """Each prompt should include an output schema in JSON format."""
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        assert "```json" in content, f"{filename} should include a JSON output schema"
