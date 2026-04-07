from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = SKILL_ROOT / "skill.yaml"
SKILL = SKILL_ROOT / "SKILL.md"
DECISION_RULES = SKILL_ROOT / "references" / "decision-rules.md"
ENV_FIX_POLICY = SKILL_ROOT / "references" / "env-fix-policy.md"


def _manifest_text() -> str:
    return MANIFEST.read_text(encoding="utf-8")


def test_manifest_contract_fields_present():
    text = _manifest_text()
    assert 'name: "readiness-agent"' in text
    assert 'display_name: "Readiness Agent"' in text
    assert 'version: "0.2.0"' in text
    assert 'type: "manual"' in text
    assert 'path: "SKILL.md"' in text
    assert 'network: "optional"' in text
    assert 'filesystem: "workspace-write"' in text


def test_manifest_keeps_core_inputs_and_drops_low_value_ones():
    text = _manifest_text()
    for token in (
        'name: "working_dir"',
        'name: "target"',
        'choices: ["training", "inference", "auto"]',
        'name: "framework_hint"',
        'choices: ["mindspore", "pta", "mixed", "auto"]',
        'name: "cann_path"',
        'name: "confirm_managed_cann"',
        'name: "mode"',
        'choices: ["check", "fix"]',
        'name: "selected_python"',
        'name: "model_hub_id"',
        'name: "dataset_hub_id"',
        'name: "dataset_split"',
        'name: "task_smoke_cmd"',
    ):
        assert token in text
    for removed in ('name: "selected_env_root"', 'name: "fix_scope"', 'name: "factory_root"', 'name: "allow_network"'):
        assert removed not in text


def test_skill_describes_streamlined_runtime_smoke_workflow():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: readiness-agent\ndescription:")
    assert "Use when Codex needs" not in text
    assert "# Readiness Agent" in text
    assert "## Scope" in text
    assert "## Hard Rules" in text
    assert "## Workflow" in text
    assert "## References" in text
    assert "## Scripts" in text
    assert "runtime_smoke" in text
    assert "`scripts/run_readiness_pipeline.py`" in text
    assert "`scripts/readiness_core.py`" not in text
    assert "`scripts/readiness_report.py`" not in text
    assert "`scripts/ascend_compat.py`" not in text
    assert "Do you want me to run the real model script now?" in text
    assert "workspace-local CANN" in text
    assert "Treat explicit Ascend runtime environment variables as authoritative runtime" in text
    assert "Before using an auto-detected installed CANN or installing a managed" in text
    assert "`allow_network`" not in text
    assert "`references/product-contract.md`" in text
    assert "`references/decision-rules.md`" in text
    assert "`references/env-fix-policy.md`" in text
    assert "`references/ascend-compat.md`" in text
    assert "Do not scan unactivated global, user-level, shared, or system environment" in text
    assert "If the entrypoint returns `BLOCKED`, summarize the blocker and stop." in text


def test_decision_rules_keep_python_and_boundary_scope_narrow():
    text = DECISION_RULES.read_text(encoding="utf-8")
    assert "only select Python from explicit user input, a workspace-local virtual" in text
    assert "do not scan unactivated global, user-level, shared, or system environment" in text
    assert "do not run broad environment inventory commands such as `conda env list`" in text
    assert "if the readiness entrypoint returns `BLOCKED`, stop and report that blocker" in text
    assert "explicit artifact URL override or a workspace-local" in text
    assert "generic local/offline artifact fallbacks" not in text


def test_env_fix_policy_forbids_host_wide_env_hunting_after_blocked():
    text = ENV_FIX_POLICY.read_text(encoding="utf-8")
    assert "scan unactivated global, user-level, shared, or system Python environment" in text
    assert "activate or switch into an arbitrary non-workspace environment" in text
    assert "continue with ad hoc shell-based host diagnosis after the readiness entrypoint" in text
    assert "workspace already caches the" in text
