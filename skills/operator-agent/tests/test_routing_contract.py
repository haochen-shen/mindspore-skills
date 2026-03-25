from pathlib import Path

import yaml


SKILL_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
ROUTING_CASES = TESTS_DIR / "routing_cases.yaml"
SKILL_MD = SKILL_ROOT / "SKILL.md"
METHOD_SELECTION = SKILL_ROOT / "references" / "method-selection.md"
VERIFICATION = SKILL_ROOT / "references" / "verification.md"

CANONICAL_METHODS = {"custom-access", "native-framework"}
CANONICAL_BACKENDS = {"CPU", "GPU", "NPU"}
EXPECTED_CASE_IDS = {
    "cpu_custom_access_default",
    "cpu_native_override",
    "npu_alias_ascend",
    "npu_alias_aclnn",
    "gpu_roadmap",
    "op_info_verification_branch",
}


def load_routing_cases():
    return yaml.safe_load(ROUTING_CASES.read_text(encoding="utf-8"))


def case_map(data):
    return {case["id"]: case for case in data["cases"]}


def test_routing_cases_yaml_exists_and_has_expected_cases():
    assert ROUTING_CASES.exists(), f"Missing routing case contract: {ROUTING_CASES}"
    data = load_routing_cases()
    assert data["schema_version"] == "1.0.0"
    assert {case["id"] for case in data["cases"]} == EXPECTED_CASE_IDS


def test_all_cases_use_valid_backends_and_methods():
    data = load_routing_cases()
    for case in data["cases"]:
        assert isinstance(case["input"]["known_evidence"], str)
        expected = case["expected"]
        assert expected["normalized_backend"] in CANONICAL_BACKENDS
        assert expected["best_fit"] in CANONICAL_METHODS | {"Roadmap"}
        assert isinstance(expected["ask_clarification"], bool)
        assert expected["require_api_resolution"] is True
        for option in expected["support_options"]:
            assert option["method"] in CANONICAL_METHODS
            assert option["status"] in {"recommended", "available", "standard", "planned"}


def test_npu_aliases_normalize_to_npu_and_select_native_framework():
    data = case_map(load_routing_cases())
    for case_id, raw_value in {
        "npu_alias_ascend": "Ascend",
        "npu_alias_aclnn": "aclnn",
    }.items():
        case = data[case_id]
        assert case["input"]["target_backend_raw"] == raw_value
        assert case["expected"]["normalized_backend"] == "NPU"
        assert case["expected"]["best_fit"] == "native-framework"


def test_cpu_and_gpu_routing_contracts():
    data = case_map(load_routing_cases())

    assert data["cpu_custom_access_default"]["expected"]["best_fit"] == "custom-access"
    assert data["cpu_custom_access_default"]["expected"]["ask_clarification"] is False

    assert data["cpu_native_override"]["expected"]["best_fit"] == "native-framework"
    assert data["cpu_native_override"]["expected"]["ask_clarification"] is False

    assert data["gpu_roadmap"]["expected"]["normalized_backend"] == "GPU"
    assert data["gpu_roadmap"]["expected"]["best_fit"] == "Roadmap"


def test_skill_md_contains_router_rules_and_imported_workflows():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "# Op Agent" in text
    assert "## MindSpore API Resolution" in text
    assert "Normalize backend aliases before routing. `Ascend` and `aclnn` both map to" in text
    assert "`cpu-plugin-builder` -> `custom-access`" in text
    assert "`npu-native-builder` -> `native-framework`" in text
    assert "workflows/native-framework/mindspore/npu-aclnn/" in text
    assert "workflows/verification/mindspore/op-info/" in text
    assert "`scripts/remote_runner_client.py`" in text


def test_reference_docs_capture_method_and_verification_policy():
    method_text = METHOD_SELECTION.read_text(encoding="utf-8")
    verification_text = VERIFICATION.read_text(encoding="utf-8")
    assert "Normalize `Ascend` and `aclnn` to `NPU`." in method_text
    assert "CPU default: `custom-access`" in method_text
    assert "NPU default: `native-framework`" in method_text
    assert "op_info" in verification_text
    assert "remote deploy-and-test" in verification_text


def test_imported_assets_exist():
    expected_paths = [
        SKILL_ROOT / "references" / "api-resolution.md",
        SKILL_ROOT / "references" / "api-to-operator.md",
        SKILL_ROOT / "references" / "backend-dispatch.md",
        SKILL_ROOT / "references" / "operator-to-backend.md",
        SKILL_ROOT / "references" / "api-helper" / "validation_checklist.md",
        SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "_shared" / "reference.md",
        SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "_shared" / "aclnn_doc",
        SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "npu-aclnn" / "00-pre-checks.md",
        SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "npu-aclnn" / "09-docs.md",
        SKILL_ROOT / "workflows" / "verification" / "mindspore" / "op-info" / "op_info_generation.md",
        SKILL_ROOT / "workflows" / "verification" / "mindspore" / "op-info" / "remote_deploy_and_test.md",
        SKILL_ROOT / "templates" / "aclnn" / "feature-document.md",
        SKILL_ROOT / "templates" / "op-info" / "summary.template.json",
        SKILL_ROOT / "scripts" / "remote_runner_client.py",
        SKILL_ROOT / "scripts" / "probe_pta_sparse_flash_attention.py",
    ]
    for path in expected_paths:
        assert path.exists(), f"Missing imported operator-agent asset: {path}"
