import re
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES_DIR = SKILL_ROOT / "references"

EXPECTED_REFERENCE_FILES = [
    "ascend-compat.md",
    "nvidia-compat.md",
]


@pytest.fixture
def skill_md_content():
    return (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")


class TestReferenceFilesExist:
    """Verify that all reference files required by SKILL.md are present."""

    @pytest.mark.parametrize("filename", EXPECTED_REFERENCE_FILES)
    def test_reference_file_exists(self, filename):
        path = REFERENCES_DIR / filename
        assert path.exists(), f"Missing reference file: {path}"

    @pytest.mark.parametrize("filename", EXPECTED_REFERENCE_FILES)
    def test_reference_file_not_empty(self, filename):
        path = REFERENCES_DIR / filename
        content = path.read_text(encoding="utf-8").strip()
        assert len(content) > 100, f"Reference file too short: {path}"


class TestAscendCompatFormat:
    """Validate ascend-compat.md has the expected table structure."""

    @pytest.fixture
    def content(self):
        return (REFERENCES_DIR / "ascend-compat.md").read_text(encoding="utf-8")

    def test_has_mindspore_cann_table(self, content):
        assert "MindSpore" in content and "CANN" in content

    def test_has_driver_table(self, content):
        assert "NPU Driver" in content

    def test_has_at_least_3_version_rows(self, content):
        # Match rows like "| 2.5.0 |" or "| 8.0.RC3 |"
        rows = re.findall(r"^\|\s*\d+\.\d+", content, re.MULTILINE)
        assert len(rows) >= 3, f"Expected >=3 version rows, found {len(rows)}"


class TestNvidiaCompatFormat:
    """Validate nvidia-compat.md has the expected table structure."""

    @pytest.fixture
    def content(self):
        return (REFERENCES_DIR / "nvidia-compat.md").read_text(encoding="utf-8")

    def test_has_pytorch_cuda_table(self, content):
        assert "PyTorch" in content and "CUDA" in content

    def test_has_driver_table(self, content):
        assert "Min Driver" in content

    def test_has_at_least_3_version_rows(self, content):
        rows = re.findall(r"^\|\s*\d+\.\d+", content, re.MULTILINE)
        assert len(rows) >= 3, f"Expected >=3 version rows, found {len(rows)}"


class TestSkillMdReferencesConsistency:
    """Ensure SKILL.md references match actual files in references/."""

    def test_skill_md_references_ascend_compat(self, skill_md_content):
        assert "references/ascend-compat.md" in skill_md_content

    def test_skill_md_references_nvidia_compat(self, skill_md_content):
        assert "references/nvidia-compat.md" in skill_md_content
