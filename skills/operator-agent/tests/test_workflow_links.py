from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ACLNN_WORKFLOW_ROOT = (
    SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "npu-aclnn"
)
ACLNN_SHARED_ROOT = (
    SKILL_ROOT / "workflows" / "native-framework" / "mindspore" / "_shared"
)


def test_op_info_workflow_uses_local_operator_agent_paths():
    path = (
        SKILL_ROOT
        / "workflows"
        / "verification"
        / "mindspore"
        / "op-info"
        / "op_info_generation.md"
    )
    text = path.read_text(encoding="utf-8")
    assert "standalone test files is not allowed" in text
    assert "../../_shared/reference.md" not in text


def test_aclnn_workflow_shared_reference_assets_exist_locally():
    assert (ACLNN_SHARED_ROOT / "reference.md").exists()
    assert (ACLNN_SHARED_ROOT / "aclnn_doc").is_dir()


def test_aclnn_workflow_files_only_reference_local_shared_assets():
    for path in ACLNN_WORKFLOW_ROOT.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "../_shared/reference.md" in text:
            assert (ACLNN_SHARED_ROOT / "reference.md").exists(), path
        if "../_shared/aclnn_doc/" in text:
            assert (ACLNN_SHARED_ROOT / "aclnn_doc").is_dir(), path


def test_reference_docs_only_point_to_existing_local_reference_files():
    expected = {
        "./api-to-operator.md": SKILL_ROOT / "references" / "api-to-operator.md",
        "./operator-to-backend.md": SKILL_ROOT / "references" / "operator-to-backend.md",
    }
    docs = [
        SKILL_ROOT / "references" / "api-resolution.md",
        SKILL_ROOT / "references" / "backend-dispatch.md",
        SKILL_ROOT / "references" / "api-helper" / "validation_checklist.md",
    ]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for needle, target in expected.items():
            assert needle in text
            assert target.exists(), f"{doc} points to missing file: {target}"
