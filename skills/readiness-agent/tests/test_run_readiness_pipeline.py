import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
READINESS_VERDICT_REF = Path("meta/readiness-verdict.json")


def run_pipeline(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "run_readiness_pipeline.py"), *args],
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )


def load_report_pair(report_json: Path) -> tuple[dict, dict]:
    envelope = json.loads(report_json.read_text(encoding="utf-8"))
    verdict_json = report_json.parent / READINESS_VERDICT_REF
    verdict = json.loads(verdict_json.read_text(encoding="utf-8"))
    return envelope, verdict


def fake_uv_source() -> str:
    return f"""#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

REAL_PYTHON = r'''{sys.executable}'''

def main() -> int:
    args = sys.argv[1:]
    if not args:
        return 1
    if args[0] == "venv":
        env_root = None
        for item in args[1:]:
            if item.startswith("-"):
                continue
            env_root = Path(item)
            break
        if env_root is None:
            return 2
        target = env_root / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_PYTHON, target)
        return 0
    if len(args) >= 2 and args[0] == "pip" and args[1] == "install":
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def install_fake_uv(tmp_path: Path, monkeypatch) -> Path:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()

    uv_py = bin_dir / "uv"
    uv_py.write_text(fake_uv_source(), encoding="utf-8")
    uv_py.chmod(uv_py.stat().st_mode | 0o111)

    uv_cmd = bin_dir / "uv.cmd"
    uv_cmd.write_text(f'@echo off\r\n"{sys.executable}" "%~dp0uv" %*\r\n', encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return bin_dir


def make_workspace(tmp_path: Path, script_name: str = "infer.py", body: str = "print('infer')\n") -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / script_name).write_text(body, encoding="utf-8")
    (workspace / "model").mkdir()
    return workspace


def make_fake_cann_dir(root: Path, version: str = "8.5.0") -> Path:
    toolkit = root / "ascend-toolkit"
    (toolkit / "opp").mkdir(parents=True, exist_ok=True)
    (toolkit / "python" / "site-packages").mkdir(parents=True, exist_ok=True)
    (toolkit / "set_env.sh").write_text(
        "#!/usr/bin/env bash\n"
        f"export ASCEND_HOME_PATH={toolkit}\n"
        f"export ASCEND_OPP_PATH={toolkit / 'opp'}\n",
        encoding="utf-8",
    )
    (toolkit / "version.info").write_text(f"version={version}\n", encoding="utf-8")
    return root


def configure_supported_linux_host(monkeypatch, arch: str = "x86_64", driver: str = "24.1.0", firmware: str = "7.3.0") -> None:
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "linux")
    monkeypatch.setenv("READINESS_HOST_ARCH", arch)
    monkeypatch.setenv("READINESS_DRIVER_VERSION", driver)
    monkeypatch.setenv("READINESS_FIRMWARE_VERSION", firmware)


def make_fake_cann_artifact(artifact_root: Path, version: str = "8.5.0", arch: str = "x86_64") -> tuple[Path, str]:
    staging_root = artifact_root / "staging"
    make_fake_cann_dir(staging_root, version=version)
    file_name = f"cann-{version}-linux-{arch}.zip"
    zip_path = artifact_root / file_name
    with zipfile.ZipFile(zip_path, "w") as archive:
        for file_path in staging_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging_root))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return zip_path, digest


def test_run_readiness_pipeline_check_blocks_without_workspace_env(tmp_path: Path):
    workspace = make_workspace(tmp_path)
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    fix_applied = verdict["fix_applied"]
    readiness_env = (workspace / ".readiness.env").read_text(encoding="utf-8")

    assert verdict["status"] == "BLOCKED"
    assert verdict["can_run"] is False
    assert fix_applied["execute"] is False
    assert fix_applied["planned_actions"]
    assert "READINESS_WORKING_DIR" in readiness_env


def test_run_readiness_pipeline_ready_uses_runtime_smoke_and_prompts_to_run_model_script(tmp_path: Path, fake_selected_python: Path):
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"
    cann_root = make_fake_cann_dir(tmp_path / "explicit-cann", version="8.5.0")

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--cann-path",
        str(cann_root),
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    assert verdict["status"] == "READY"
    assert verdict["can_run"] is True
    assert verdict["evidence_level"] == "runtime_smoke"
    assert "Do you want me to run the real model script now?" in verdict["next_action"]


def test_run_readiness_pipeline_blocks_on_invalid_explicit_cann_path(tmp_path: Path, fake_selected_python: Path):
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--cann-path",
        str(tmp_path / "custom-cann-9.9.9"),
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    assert verdict["status"] == "BLOCKED"
    assert any(item["id"] == "cann-runtime" for item in verdict["blockers_detailed"])


def test_run_readiness_pipeline_fix_stops_on_invalid_explicit_cann_path(tmp_path: Path, fake_selected_python: Path):
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--cann-path",
        str(tmp_path / "custom-cann-9.9.9"),
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    env_json = json.loads((output_dir / "meta" / "env.json").read_text(encoding="utf-8"))
    assert verdict["status"] == "BLOCKED"
    assert verdict["fix_applied"]["executed_actions"] == []
    assert verdict["fix_applied"]["terminal_failure"]["id"] == "cann-runtime"
    assert not (workspace / ".venv").exists()
    assert env_json["pipeline_passes"] == 1


def test_run_readiness_pipeline_fix_stops_on_invalid_explicit_ascend_env_input(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"
    monkeypatch.setenv("ASCEND_HOME_PATH", str((tmp_path / "broken-ascend").resolve()))

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    env_json = json.loads((output_dir / "meta" / "env.json").read_text(encoding="utf-8"))
    assert verdict["status"] == "BLOCKED"
    assert verdict["fix_applied"]["executed_actions"] == []
    assert verdict["fix_applied"]["terminal_failure"]["id"] == "cann-runtime"
    assert any("explicit Ascend environment variables" in item["summary"] for item in verdict["blockers_detailed"])
    assert not (workspace / ".venv").exists()
    assert env_json["pipeline_passes"] == 1


def test_run_readiness_pipeline_fix_creates_default_env_and_reruns(tmp_path: Path, monkeypatch):
    install_fake_uv(tmp_path, monkeypatch)
    workspace = make_workspace(tmp_path)
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--model-path",
        "model",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    env_json = json.loads((output_dir / "meta" / "env.json").read_text(encoding="utf-8"))

    assert (workspace / ".venv").exists()
    assert verdict["status"] == "WARN"
    assert verdict["can_run"] is True
    assert "Do you want me to run the real model script now?" in verdict["next_action"]
    assert env_json["pipeline_passes"] == 2
    assert "create-workspace-env" in verdict["fix_applied"]["executed_actions"]


def test_run_readiness_pipeline_check_blocks_when_cann_is_missing_but_fix_can_repair(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    _, checksum = make_fake_cann_artifact(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_SHA256_X86_64_8_5_0", checksum)

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    cann_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "cann-runtime")
    assert verdict["status"] == "BLOCKED"
    assert cann_blocker["remediable"] is True
    assert cann_blocker["confirmation_required"] is True
    assert any(option["kind"] == "managed_workspace_cann" for option in cann_blocker["confirmation_options"])


def test_run_readiness_pipeline_check_blocks_with_clear_cann_reason_on_unsupported_host(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "darwin")
    monkeypatch.setenv("READINESS_HOST_ARCH", "x86_64")
    monkeypatch.delenv("READINESS_DRIVER_VERSION", raising=False)
    monkeypatch.delenv("READINESS_FIRMWARE_VERSION", raising=False)

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    cann_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "cann-runtime")
    assert verdict["status"] == "BLOCKED"
    assert cann_blocker["remediable"] is False
    assert "does not support managed workspace-local CANN" in cann_blocker["summary"]


def test_run_readiness_pipeline_check_blocks_with_clear_cann_reason_when_driver_is_unresolved(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "linux")
    monkeypatch.setenv("READINESS_HOST_ARCH", "x86_64")
    monkeypatch.delenv("READINESS_DRIVER_VERSION", raising=False)
    monkeypatch.setenv("READINESS_FIRMWARE_VERSION", "7.3.0")

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    cann_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "cann-runtime")
    assert verdict["status"] == "BLOCKED"
    assert cann_blocker["remediable"] is False
    assert "could not determine the host driver version" in cann_blocker["summary"]


def test_run_readiness_pipeline_fix_installs_workspace_cann_and_reruns(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    _, checksum = make_fake_cann_artifact(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_SHA256_X86_64_8_5_0", checksum)

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--confirm-managed-cann",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    readiness_env = (workspace / ".readiness.env").read_text(encoding="utf-8")
    assert verdict["status"] == "READY"
    assert "install-workspace-cann" in verdict["fix_applied"]["executed_actions"]
    assert (workspace / "cann" / "8.5.0").exists()
    assert "READINESS_SELECTED_CANN_VERSION='8.5.0'" in readiness_env or "READINESS_SELECTED_CANN_VERSION=8.5.0" in readiness_env


def test_run_readiness_pipeline_fix_stops_when_workspace_cann_install_fails(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    _, checksum = make_fake_cann_artifact(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_SHA256_X86_64_8_5_0", "0" * len(checksum))

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--confirm-managed-cann",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    assert verdict["status"] == "BLOCKED"
    assert "install-workspace-cann" in verdict["fix_applied"]["failed_actions"]
    assert verdict["fix_applied"]["terminal_failure"]["id"] == "cann-runtime"
    assert any("Readiness could not install a usable workspace-local CANN package." == item["summary"] for item in verdict["blockers_detailed"])


def test_run_readiness_pipeline_reuses_existing_managed_cann_without_reinstall(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    make_fake_cann_dir(workspace / "cann" / "8.5.0", version="8.5.0")
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    assert verdict["status"] == "READY"
    assert "install-workspace-cann" not in verdict["fix_applied"]["executed_actions"]


def test_run_readiness_pipeline_fix_stops_when_managed_cann_install_needs_confirmation(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    _, checksum = make_fake_cann_artifact(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_SHA256_X86_64_8_5_0", checksum)

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    cann_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "cann-runtime")
    assert verdict["status"] == "BLOCKED"
    assert verdict["fix_applied"]["executed_actions"] == []
    assert verdict["fix_applied"]["terminal_failure"]["id"] == "cann-runtime"
    assert cann_blocker["confirmation_required"] is True
    assert any(option["kind"] == "managed_workspace_cann" for option in cann_blocker["confirmation_options"])


def test_run_readiness_pipeline_check_requires_confirmation_before_using_bounded_search_cann(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    home_root = tmp_path / "home"
    home_root.mkdir()
    candidate_root = make_fake_cann_dir(home_root / "cann-8.5.0", version="8.5.0")
    monkeypatch.setenv("HOME", str(home_root))

    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    cann_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "cann-runtime")
    assert verdict["status"] == "BLOCKED"
    assert cann_blocker["confirmation_required"] is True
    existing_options = [option for option in cann_blocker["confirmation_options"] if option["kind"] == "existing_cann"]
    assert existing_options
    assert any(str(candidate_root) in option["path"] for option in existing_options)


def test_run_readiness_pipeline_prefers_explicit_ascend_env_input_over_managed_workspace(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
    )
    managed_root = make_fake_cann_dir(workspace / "cann" / "8.3.RC1", version="8.3.RC1")
    explicit_env_root = make_fake_cann_dir(tmp_path / "env-cann", version="8.5.0")
    monkeypatch.setenv("ASCEND_HOME_PATH", str((explicit_env_root / "ascend-toolkit").resolve()))
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--check",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    system_layer = verdict["dependency_closure"]["layers"]["system"]
    assert verdict["status"] == "READY"
    assert system_layer["selected_cann_source"] == "env_input"
    assert str(explicit_env_root) in system_layer["selected_cann_path"]
    assert str(managed_root) not in system_layer["selected_cann_path"]


def test_run_readiness_pipeline_tolerates_missing_and_unknown_cli_args(tmp_path: Path):
    workspace = make_workspace(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_readiness_pipeline.py"),
            "--check",
            "--verbose",
            "--unknown-flag",
            "mystery",
            "--model-path",
        ],
        cwd=str(workspace),
        check=True,
        text=True,
        capture_output=True,
    )

    summary = json.loads(completed.stdout)
    inputs = json.loads((workspace / "readiness-output" / "meta" / "inputs.json").read_text(encoding="utf-8"))

    assert summary["status"] == "BLOCKED"
    assert inputs["ignored_cli_args"] == [
        {"token": "--unknown-flag", "reason": "unknown_flag"},
        {"token": "mystery", "reason": "unknown_flag_value"},
        {"token": "--model-path", "reason": "missing_value"},
    ]


def test_run_readiness_pipeline_rejects_removed_auto_mode(tmp_path: Path):
    workspace = make_workspace(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_readiness_pipeline.py"),
            "--auto",
        ],
        cwd=str(workspace),
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "error": "auto mode was removed; use --fix for readiness remediation."
    }
