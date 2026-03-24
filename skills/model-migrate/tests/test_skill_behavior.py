from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"


def test_model_migrate_is_top_level_entry():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "This skill is the top-level migration entry." in text
    assert "The user should not need to decide" in text
    assert "whether the case belongs to Hugging Face transformers, Hugging Face" in text


def test_route_selection_and_reuse_rules_are_present():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "Choose exactly one migration route:" in text
    assert "- `hf-transformers`" in text
    assert "- `hf-diffusers`" in text
    assert "- `generic-pytorch-repo`" in text
    assert "Reuse the existing `hf-transformers-migrate`, `hf-diffusers-migrate`, and" in text


def test_references_and_scripts_are_declared():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "`references/migration-routing.md`" in text
    assert "`references/verification.md`" in text
    assert "`scripts/collect_migration_context.py`" in text
    assert "`scripts/summarize_migration_profile.py`" in text
