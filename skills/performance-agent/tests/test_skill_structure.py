from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"


def test_skill_markers_present():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "## Workflow" in text
    assert "## Stage 1. Performance Analyzer" in text
    assert "## Stage 2. Bottleneck Validator" in text
    assert "## Stage 3. Snapshot Builder" in text
    assert "## Stage 4. Report Builder" in text


def test_reference_files_exist():
    assert (SKILL_ROOT / "references" / "perf-validation.md").exists()
    assert (SKILL_ROOT / "contract" / "performance-verdict.schema.json").exists()
