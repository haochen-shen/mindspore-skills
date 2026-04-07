import hashlib
import json
import os
import subprocess
import sys
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


def make_active_python_env(root: Path) -> Path:
    bin_dir = root / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        python_path = bin_dir / "python.exe"
        python_path.write_bytes(Path(sys.executable).read_bytes())
        return root

    python_path = bin_dir / "python"
    python_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        f"REAL_PYTHON = r'''{sys.executable}'''\n"
        "if len(sys.argv) >= 3 and sys.argv[1] == '-c':\n"
        "    code = sys.argv[2]\n"
        "    if 'platform.python_version' in code and 'version_info' in code:\n"
        "        print(json.dumps({'version_info': [3, 10, 0], 'version': '3.10.0'}))\n"
        "        raise SystemExit(0)\n"
        "completed = subprocess.run([REAL_PYTHON, *sys.argv[1:]])\n"
        "raise SystemExit(completed.returncode)\n",
        encoding="utf-8",
    )
    python_path.chmod(python_path.stat().st_mode | 0o111)
    return root


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
    monkeypatch.setenv("READINESS_CHIP_TYPE", "910b")


def _fake_run_package_source(package_kind: str, version: str, chip_type: str = "910b") -> str:
    if package_kind == "toolkit":
        return f"""#!/usr/bin/env bash
set -e
install_path=""
for arg in "$@"; do
  case "$arg" in
    --install-path=*) install_path="${{arg#*=}}" ;;
  esac
done
[ -n "$install_path" ] || exit 11
mkdir -p "$install_path/cann/opp" "$install_path/cann/python/site-packages" "$install_path/cann/latest/share/info/metadef" "$install_path/cann/x86_64-linux"
cat > "$install_path/cann/set_env.sh" <<EOF
#!/usr/bin/env bash
export ASCEND_HOME_PATH=$install_path/cann
export ASCEND_TOOLKIT_HOME=$install_path/cann
export ASCEND_TOOLKIT_PATH=$install_path/cann
export ASCEND_OPP_PATH=$install_path/cann/opp
export TBE_IMPL_PATH=$install_path/cann/python/site-packages
EOF
printf 'Version={version}\\n' > "$install_path/cann/latest/share/info/metadef/version.info"
printf 'version={version}\\n' > "$install_path/cann/version.info"
"""
    return f"""#!/usr/bin/env bash
set -e
install_path=""
package_type=""
for arg in "$@"; do
  case "$arg" in
    --install-path=*) install_path="${{arg#*=}}" ;;
    --type=*) package_type="${{arg#*=}}" ;;
  esac
done
[ -n "$install_path" ] || exit 21
[ "$package_type" = "toolkit" ] || exit 22
[ -f "$install_path/cann/set_env.sh" ] || exit 23
mkdir -p "$install_path/cann/ops/{chip_type}"
printf 'ops={chip_type}\\n' > "$install_path/cann/ops/{chip_type}/install.info"
"""


def make_fake_cann_artifacts(artifact_root: Path, version: str = "8.5.0", arch: str = "x86_64", chip_type: str = "910b") -> dict:
    toolkit_name = f"Ascend-cann-toolkit_{version}_linux-{arch}.run"
    ops_name = f"Ascend-cann-{chip_type}-ops_{version}_linux-{arch}.run"
    toolkit_path = artifact_root / toolkit_name
    ops_path = artifact_root / ops_name
    toolkit_path.write_bytes(_fake_run_package_source("toolkit", version=version, chip_type=chip_type).encode("utf-8"))
    ops_path.write_bytes(_fake_run_package_source("ops", version=version, chip_type=chip_type).encode("utf-8"))
    return {
        "toolkit_path": toolkit_path,
        "toolkit_sha256": hashlib.sha256(toolkit_path.read_bytes()).hexdigest(),
        "ops_path": ops_path,
        "ops_sha256": hashlib.sha256(ops_path.read_bytes()).hexdigest(),
    }


def test_run_readiness_pipeline_check_blocks_without_workspace_env(tmp_path: Path, monkeypatch):
    workspace = make_workspace(tmp_path)
    output_dir = tmp_path / "out"
    cann_root = make_fake_cann_dir(tmp_path / "explicit-cann", version="8.5.0")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--model-path",
        "model",
        "--cann-path",
        str(cann_root),
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


def test_run_readiness_pipeline_check_uses_active_shell_env_when_workspace_env_missing(tmp_path: Path, monkeypatch):
    workspace = make_workspace(tmp_path, body="import torch\nprint('infer')\n")
    output_dir = tmp_path / "out"
    active_env = make_active_python_env(tmp_path / "active-venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(active_env))

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
    python_layer = verdict["dependency_closure"]["layers"]["python_environment"]

    assert verdict["status"] == "BLOCKED"
    assert python_layer["selection_source"] == "active_shell_env"
    assert python_layer["selection_status"] == "selected"
    assert any(item["id"] == "framework-selection" for item in verdict["blockers_detailed"])
    assert not any(item["id"] == "python-selected-env" for item in verdict["blockers_detailed"])


def test_run_readiness_pipeline_fix_stops_when_framework_confirmation_is_missing(tmp_path: Path, fake_selected_python: Path):
    workspace = make_workspace(
        tmp_path,
        body="import torch\nimport torch_npu\nfrom transformers import Trainer\nprint('train')\n",
    )
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--selected-python",
        str(fake_selected_python),
        "--model-path",
        "model",
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    framework_blocker = next(item for item in verdict["blockers_detailed"] if item["id"] == "framework-selection")

    assert verdict["status"] == "BLOCKED"
    assert verdict["fix_applied"]["executed_actions"] == []
    assert verdict["fix_applied"]["terminal_failure"]["id"] == "framework-selection"
    assert framework_blocker["confirmation_required"] is True
    assert any(option["framework"] == "pta" for option in framework_blocker["confirmation_options"])


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
    cann_root = make_fake_cann_dir(tmp_path / "explicit-cann", version="8.5.0")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--framework-hint",
        "pta",
        "--model-path",
        "model",
        "--cann-path",
        str(cann_root),
        "--fix",
        cwd=workspace,
    )

    _, verdict = load_report_pair(output_dir / "report.json")
    env_json = json.loads((output_dir / "meta" / "env.json").read_text(encoding="utf-8"))

    assert (workspace / ".venv").exists()
    assert verdict["status"] == "BLOCKED"
    assert verdict["can_run"] is False
    assert env_json["pipeline_passes"] >= 2
    assert "create-workspace-env" in verdict["fix_applied"]["executed_actions"]


def test_run_readiness_pipeline_check_blocks_when_cann_is_missing_but_fix_can_repair(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    artifacts = make_fake_cann_artifacts(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_TOOLKIT_SHA256_TOOLKIT_X86_64_8_5_0", artifacts["toolkit_sha256"])
    monkeypatch.setenv("READINESS_CANN_OPS_SHA256_OPS_X86_64_8_5_0_910B", artifacts["ops_sha256"])

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
    artifacts = make_fake_cann_artifacts(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_TOOLKIT_SHA256_TOOLKIT_X86_64_8_5_0", artifacts["toolkit_sha256"])
    monkeypatch.setenv("READINESS_CANN_OPS_SHA256_OPS_X86_64_8_5_0_910B", artifacts["ops_sha256"])

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
    assert "READINESS_SELECTED_CANN_SOURCE" not in readiness_env


def test_run_readiness_pipeline_fix_stops_when_workspace_cann_install_fails(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    configure_supported_linux_host(monkeypatch)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    artifacts = make_fake_cann_artifacts(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_TOOLKIT_SHA256_TOOLKIT_X86_64_8_5_0", "0" * len(artifacts["toolkit_sha256"]))
    monkeypatch.setenv("READINESS_CANN_OPS_SHA256_OPS_X86_64_8_5_0_910B", artifacts["ops_sha256"])

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
    artifacts = make_fake_cann_artifacts(artifact_root)
    monkeypatch.setenv("READINESS_CANN_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("READINESS_CANN_TOOLKIT_SHA256_TOOLKIT_X86_64_8_5_0", artifacts["toolkit_sha256"])
    monkeypatch.setenv("READINESS_CANN_OPS_SHA256_OPS_X86_64_8_5_0_910B", artifacts["ops_sha256"])

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
