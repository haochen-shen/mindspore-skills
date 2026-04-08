import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_pipeline(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "run_new_readiness_pipeline.py"), *args],
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )


def stdout_payload(completed: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(completed.stdout)


def current_field(summary: dict) -> Optional[str]:
    current_confirmation = summary.get("current_confirmation")
    if not isinstance(current_confirmation, dict):
        return None
    return current_confirmation.get("field")


def current_options(summary: dict) -> list[str]:
    current_confirmation = summary.get("current_confirmation")
    if not isinstance(current_confirmation, dict):
        return []
    return [str(option.get("value")) for option in current_confirmation.get("options", [])]


def test_pipeline_requires_confirmation_before_final_verdict(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("print('infer')\n", encoding="utf-8")
    (workspace / "model").mkdir()
    output_dir = tmp_path / "out"

    completed = run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--entry-script",
        "infer.py",
        "--model-path",
        "model",
        "--launch-command",
        "python infer.py",
        cwd=workspace,
    )

    verdict = json.loads((output_dir / "meta" / "readiness-verdict.json").read_text(encoding="utf-8"))
    summary = stdout_payload(completed)
    assert verdict["status"] == "NEEDS_CONFIRMATION"
    assert verdict["phase"] == "awaiting_confirmation"
    assert verdict["confirmation_required"] is True
    assert verdict["can_run"] is False
    assert verdict["current_confirmation"]["field"] == "launcher"
    assert summary["confirmation_required"] is True
    assert current_field(summary) == "launcher"
    assert (workspace / "runs" / "latest" / "new-readiness-agent" / "workspace-readiness.lock.json").exists()


def test_pipeline_warns_but_can_run_and_writes_latest_cache(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train.py").write_text("import torch\nimport torch_npu\nfrom transformers import Trainer\n", encoding="utf-8")
    (workspace / "train.yaml").write_text("model_name_or_path: model\ntrain_file: dataset/sample.txt\n", encoding="utf-8")
    (workspace / "model").mkdir()
    (workspace / "dataset").mkdir()
    (workspace / "dataset" / "sample.txt").write_text("hello\n", encoding="utf-8")
    cann_root = tmp_path / "cann"
    cann_root.mkdir()
    (cann_root / "version.cfg").write_text("version=8.5.0\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--framework-hint",
        "pta",
        "--launcher-hint",
        "torchrun",
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "train.py",
        "--config-path",
        "train.yaml",
        "--model-path",
        "model",
        "--dataset-path",
        "dataset",
        "--cann-path",
        str(cann_root),
        "--launch-command",
        "torchrun train.py --config train.yaml",
        cwd=workspace,
    )

    verdict = json.loads((output_dir / "meta" / "readiness-verdict.json").read_text(encoding="utf-8"))
    latest_root = workspace / "runs" / "latest" / "new-readiness-agent"
    latest_lock = json.loads((latest_root / "workspace-readiness.lock.json").read_text(encoding="utf-8"))
    confirmation = json.loads((latest_root / "confirmation-latest.json").read_text(encoding="utf-8"))

    assert verdict["status"] == "WARN"
    assert verdict["can_run"] is True
    assert latest_lock["launcher"] == "torchrun"
    assert latest_lock["selected_python"] == str(fake_selected_python)
    assert confirmation["current_confirmation"] is None


def test_pipeline_offers_catalog_options_when_workspace_has_no_runtime_evidence(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "out"

    summary = stdout_payload(
        run_pipeline(
            "--working-dir",
            str(workspace),
            "--output-dir",
            str(output_dir),
            cwd=workspace,
        )
    )

    assert summary["status"] == "NEEDS_CONFIRMATION"
    assert current_field(summary) == "target"
    assert "training" in current_options(summary)
    assert "inference" in current_options(summary)
    assert "__unknown__" in current_options(summary)


def test_pipeline_advances_one_confirmation_step_at_a_time(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir_1 = tmp_path / "out1"
    output_dir_2 = tmp_path / "out2"
    output_dir_3 = tmp_path / "out3"

    first = stdout_payload(
        run_pipeline(
            "--working-dir",
            str(workspace),
            "--output-dir",
            str(output_dir_1),
            cwd=workspace,
        )
    )
    second = stdout_payload(
        run_pipeline(
            "--working-dir",
            str(workspace),
            "--output-dir",
            str(output_dir_2),
            "--confirm",
            "target=training",
            cwd=workspace,
        )
    )
    third = stdout_payload(
        run_pipeline(
            "--working-dir",
            str(workspace),
            "--output-dir",
            str(output_dir_3),
            "--confirm",
            "launcher=python",
            cwd=workspace,
        )
    )

    assert current_field(first) == "target"
    assert current_field(second) == "launcher"
    assert current_field(third) == "framework"


def test_pipeline_detects_llamafactory_launcher_from_explicit_command(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train.py").write_text("import torch\nimport torch_npu\nimport transformers\n", encoding="utf-8")
    (workspace / "llama_sft.yaml").write_text("stage: sft\nmodel_name_or_path: model\ntrain_file: dataset/sample.txt\n", encoding="utf-8")
    (workspace / "model").mkdir()
    (workspace / "dataset").mkdir()
    (workspace / "dataset" / "sample.txt").write_text("hello\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "train.py",
        "--config-path",
        "llama_sft.yaml",
        "--model-path",
        "model",
        "--dataset-path",
        "dataset",
        "--launch-command",
        "uv run llamafactory-cli train --config llama_sft.yaml",
        cwd=workspace,
    )

    verdict = json.loads((output_dir / "meta" / "readiness-verdict.json").read_text(encoding="utf-8"))
    assert verdict["status"] == "NEEDS_CONFIRMATION"
    assert verdict["launcher"]["value"] == "llamafactory-cli"
    assert verdict["evidence_summary"]["uses_llamafactory"] is True


def test_repeated_run_refreshes_latest_run_ref(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\nprint('infer')\n", encoding="utf-8")
    (workspace / "model").mkdir()
    cann_root = tmp_path / "cann"
    cann_root.mkdir()
    (cann_root / "version.cfg").write_text("version=8.5.0\n", encoding="utf-8")

    out1 = tmp_path / "out1"
    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(out1),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--launcher-hint",
        "python",
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "infer.py",
        "--model-path",
        "model",
        "--cann-path",
        str(cann_root),
        "--launch-command",
        "python infer.py",
        cwd=workspace,
    )

    latest_root = workspace / "runs" / "latest" / "new-readiness-agent"
    first_run_ref = json.loads((latest_root / "run-ref.json").read_text(encoding="utf-8"))

    out2 = tmp_path / "out2"
    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(out2),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--launcher-hint",
        "python",
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "infer.py",
        "--model-path",
        "model",
        "--cann-path",
        str(cann_root),
        "--launch-command",
        "python infer.py",
        cwd=workspace,
    )

    second_run_ref = json.loads((latest_root / "run-ref.json").read_text(encoding="utf-8"))
    assert first_run_ref["output_dir"] != second_run_ref["output_dir"]
