import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
READINESS_VERDICT_REF = Path("meta/readiness-verdict.json")


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    script = SCRIPTS / script_name
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def load_report_pair(report_json: Path) -> tuple[dict, dict]:
    envelope = json.loads(report_json.read_text(encoding="utf-8"))
    verdict_json = report_json.parent / READINESS_VERDICT_REF
    verdict = json.loads(verdict_json.read_text(encoding="utf-8"))
    return envelope, verdict


def fake_python_source() -> str:
    real_python = json.dumps(sys.executable)
    return f"""#!/usr/bin/env python3
import json
import subprocess
import sys

REAL_PYTHON = {real_python}

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    code = sys.argv[2]
    if "platform.python_version" in code and "version_info" in code:
        print(json.dumps({{"version_info": [3, 10, 0], "version": "3.10.0"}}))
        raise SystemExit(0)
    if "importlib.util" in code and len(sys.argv) >= 5:
        mode = sys.argv[3]
        payload = json.loads(sys.argv[4])
        if mode == "import":
            packages = payload.get("packages", [])
            print(json.dumps({{name: True for name in packages}}))
            raise SystemExit(0)
        if mode == "framework_smoke":
            print(json.dumps({{"success": True, "details": ["fake framework smoke ok"], "error": None}}))
            raise SystemExit(0)
    completed = subprocess.run([REAL_PYTHON, *sys.argv[1:]])
    raise SystemExit(completed.returncode)

if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "py_compile":
    raise SystemExit(0)

completed = subprocess.run([REAL_PYTHON, *sys.argv[1:]])
raise SystemExit(completed.returncode)
"""


def fake_uv_source() -> str:
    return """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

FAKE_PYTHON = r'''__FAKE_PYTHON__'''
REAL_PYTHON = r'''__REAL_PYTHON__'''


def write_fake_python(env_root: Path) -> None:
    if os.name == "nt":
        target = env_root / "Scripts" / "python.exe"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_PYTHON, target)
        return

    target = env_root / "bin" / "python"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(FAKE_PYTHON, encoding="utf-8")
    target.chmod(target.stat().st_mode | 0o111)


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
        write_fake_python(env_root)
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
    uv_py.write_text(
        fake_uv_source()
        .replace("__FAKE_PYTHON__", fake_python_source().replace("'''", "\\'\\'\\'"))
        .replace("__REAL_PYTHON__", sys.executable.replace("'''", "\\'\\'\\'")),
        encoding="utf-8",
    )
    uv_py.chmod(uv_py.stat().st_mode | 0o111)

    uv_cmd = bin_dir / "uv.cmd"
    uv_cmd.write_text(
        f'@echo off\r\n"{sys.executable}" "%~dp0uv" %*\r\n',
        encoding="utf-8",
    )

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return bin_dir


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text(
        "import torch\nimport torch_npu\nimport transformers\nprint('infer')\n",
        encoding="utf-8",
    )
    (workspace / "model").mkdir()
    return workspace


def test_run_readiness_pipeline_check_does_not_create_workspace_env(tmp_path: Path, monkeypatch):
    install_fake_uv(tmp_path, monkeypatch)
    workspace = make_workspace(tmp_path)
    output_dir = tmp_path / "out"

    run_script(
        "run_readiness_pipeline.py",
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--mode",
        "check",
        "--model-path",
        "model",
    )

    _, verdict = load_report_pair(output_dir / "report.json")

    assert verdict["status"] == "BLOCKED"
    assert verdict["fix_applied"]["execute"] is False
    assert verdict["fix_applied"]["executed_actions"] == []
    assert not (workspace / ".venv").exists()
    assert not (output_dir / "debug" / "state.json").exists()
    assert not (output_dir / "meta" / "execution-target.json").exists()
    assert not (output_dir / "meta" / "checks.json").exists()
    assert not (output_dir / "meta" / "fix-applied.json").exists()


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
    debug_state = json.loads((workspace / "readiness-output" / "debug" / "state.json").read_text(encoding="utf-8"))
    _, verdict = load_report_pair(workspace / "readiness-output" / "report.json")

    assert completed.stderr == ""
    assert summary["status"] == "BLOCKED"
    assert Path(inputs["working_dir"]) == workspace.resolve()
    assert inputs["verbose"] is True
    assert inputs["raw_cli_args"] == ["--check", "--verbose", "--unknown-flag", "mystery", "--model-path"]
    assert inputs["ignored_cli_args"] == [
        {"token": "--unknown-flag", "reason": "unknown_flag"},
        {"token": "mystery", "reason": "unknown_flag_value"},
        {"token": "--model-path", "reason": "missing_value"},
    ]
    assert verdict["status"] == "BLOCKED"
    assert debug_state["mode"] == "check"
    assert debug_state["initial_pass"] is not None
    assert debug_state["remediation_plan"] == {"actions": [], "skipped": []}


def test_run_readiness_pipeline_records_framework_hint(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train.py").write_text("import mindspore as ms\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_script(
        "run_readiness_pipeline.py",
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--framework-hint",
        "pta",
        "--mode",
        "check",
    )

    inputs = json.loads((output_dir / "meta" / "inputs.json").read_text(encoding="utf-8"))
    _, verdict = load_report_pair(output_dir / "report.json")
    target = verdict["execution_target"]

    assert inputs["framework_hint"] == "pta"
    assert target["framework_hint"] == "pta"
    assert target["framework_path"] == "pta"


def test_run_readiness_pipeline_records_cann_path(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "out"
    cann_root = tmp_path / "custom-cann" / "8.5.0"

    run_script(
        "run_readiness_pipeline.py",
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--cann-path",
        str(cann_root),
        "--mode",
        "check",
    )

    inputs = json.loads((output_dir / "meta" / "inputs.json").read_text(encoding="utf-8"))
    _, verdict = load_report_pair(output_dir / "report.json")
    target = verdict["execution_target"]

    assert inputs["cann_path"] == str(cann_root)
    assert target["cann_path"] == str(cann_root)


def test_run_readiness_pipeline_records_huggingface_inputs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output_dir = tmp_path / "out"

    run_script(
        "run_readiness_pipeline.py",
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--model-hub-id",
        "Qwen/Qwen3-0.6B",
        "--dataset-hub-id",
        "karthiksagarn/astro_horoscope",
        "--dataset-split",
        "train",
        "--mode",
        "check",
    )

    inputs = json.loads((output_dir / "meta" / "inputs.json").read_text(encoding="utf-8"))
    _, verdict = load_report_pair(output_dir / "report.json")
    target = verdict["execution_target"]

    assert inputs["model_hub_id"] == "Qwen/Qwen3-0.6B"
    assert inputs["dataset_hub_id"] == "karthiksagarn/astro_horoscope"
    assert inputs["dataset_split"] == "train"
    assert target["model_hub_id"] == "Qwen/Qwen3-0.6B"
    assert target["dataset_hub_id"] == "karthiksagarn/astro_horoscope"
    assert target["dataset_split"] == "train"


def test_run_readiness_pipeline_auto_creates_default_env_and_reruns(tmp_path: Path, monkeypatch):
    install_fake_uv(tmp_path, monkeypatch)
    workspace = make_workspace(tmp_path)
    output_dir = tmp_path / "out"

    run_script(
        "run_readiness_pipeline.py",
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "inference",
        "--auto",
        "--model-path",
        "model",
    )

    env_json = json.loads((output_dir / "meta" / "env.json").read_text(encoding="utf-8"))
    _, verdict = load_report_pair(output_dir / "report.json")
    checks = verdict["checks"]
    fix_applied = verdict["fix_applied"]
    selected_environment = verdict["selected_environment_guidance"]
    execution_target = verdict["execution_target"]
    by_id = {item["id"]: item for item in checks}

    assert env_json["pipeline_passes"] == 2
    assert fix_applied["execute"] is True
    assert (workspace / ".venv").exists()
    assert fix_applied["executed_actions"]
    assert execution_target["selected_python_status"] == "selected"
    assert str(workspace / ".venv") in str(execution_target["selected_env_root"])
    assert str(workspace / ".venv") in str(selected_environment["selected_env_root"])
    assert by_id["python-selected-python"]["status"] == "ok"
    assert not (output_dir / "meta" / "selected-python.json").exists()
    assert not (output_dir / "meta" / "remediation.json").exists()
    assert not (output_dir / "meta" / "execution-target.json").exists()
    assert not (output_dir / "meta" / "checks.json").exists()
