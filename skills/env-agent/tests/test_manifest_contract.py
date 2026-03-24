from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = SKILL_ROOT / "skill.yaml"
SKILL = SKILL_ROOT / "SKILL.md"


def _manifest_text() -> str:
    return MANIFEST.read_text(encoding="utf-8")


def test_manifest_contract_fields_present():
    text = _manifest_text()
    assert 'name: "env-agent"' in text
    assert 'display_name: "Env Agent"' in text
    assert 'version: "0.1.0"' in text
    assert 'type: "manual"' in text
    assert 'path: "SKILL.md"' in text
    assert 'network: "none"' in text
    assert 'filesystem: "workspace-write"' in text


def test_manifest_declares_workspace_and_factory_inputs():
    text = _manifest_text()
    assert 'name: "working_dir"' in text
    assert 'name: "mode"' in text
    assert 'choices: ["quick", "full"]' in text
    assert 'name: "factory_root"' in text
    assert 'report_schema' in text
    assert 'out_dir_layout' in text


def test_skill_describes_four_stage_workflow():
    text = SKILL.read_text(encoding="utf-8")
    assert "# Env Agent" in text
    assert "1. `workspace-analyzer`" in text
    assert "2. `compatibility-validator`" in text
    assert "3. `snapshot-builder`" in text
    assert "4. `report-builder`" in text
    assert "overall status: `READY`, `WARN`, or `BLOCKED`" in text
