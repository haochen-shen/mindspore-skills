import hashlib
import os
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler
from os import name as os_name
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "scripts").resolve()))

import readiness_core
import managed_cann
import python_selection
from readiness_core import build_state, discover_execution_target, install_packages, plan_fix_stage, probe_hf_endpoint, selected_python_for_execution
from runtime_env import detect_cann_version


class _RetryProbeHandler(BaseHTTPRequestHandler):
    api_attempts = 0

    def do_HEAD(self):
        if self.path == "/":
            self.send_response(405)
        elif self.path == "/api/models/Qwen/Qwen3-0.6B":
            type(self).api_attempts += 1
            self.send_response(200 if type(self).api_attempts >= 3 else 503)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def _args(**overrides):
    payload = {
        "target": "auto",
        "framework_hint": "auto",
        "entry_script": None,
        "selected_python": None,
        "config_path": None,
        "model_path": None,
        "model_hub_id": None,
        "dataset_path": None,
        "dataset_hub_id": None,
        "dataset_split": None,
        "checkpoint_path": None,
        "task_smoke_cmd": None,
        "cann_path": None,
        "confirm_managed_cann": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _workspace_python_path(env_root: Path) -> Path:
    if os_name == "nt":
        python_path = env_root / "Scripts" / "python.exe"
    else:
        python_path = env_root / "bin" / "python"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    return python_path


def _make_fake_cann_dir(root: Path, version: str = "8.5.0") -> Path:
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


def _set_supported_linux_host(monkeypatch, arch: str = "x86_64", driver: str = "24.1.0", firmware: str = "7.3.0") -> None:
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "linux")
    monkeypatch.setenv("READINESS_HOST_ARCH", arch)
    monkeypatch.setenv("READINESS_DRIVER_VERSION", driver)
    monkeypatch.setenv("READINESS_FIRMWARE_VERSION", firmware)
    monkeypatch.setenv("READINESS_CHIP_TYPE", "910b")


def _planned_actions(target: dict, closure: dict, normalized: dict) -> list[dict]:
    return list(plan_fix_stage(target, closure, normalized).get("actions") or [])


def test_discover_execution_target_matches_qwen_recipe_from_remote_assets(tmp_path: Path):
    target = discover_execution_target(
        tmp_path,
        _args(
            model_hub_id="Qwen/Qwen3-0.6B",
            dataset_hub_id="karthiksagarn/astro_horoscope",
        ),
    )
    assert target["target_type"] == "training"
    assert target["example_recipe_id"] == "qwen3-training"
    assert target["entry_script"].endswith("train.py")


def test_discover_execution_target_stays_inside_current_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    unrelated_repo = tmp_path / "other-project"
    unrelated_repo.mkdir()
    (unrelated_repo / "train_qwen3.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (unrelated_repo / "model").mkdir()
    (unrelated_repo / ".venv").mkdir()

    target = discover_execution_target(workspace, _args())

    assert target["working_dir"] == str(workspace)
    assert target["entry_script"] is None
    assert target["model_path"] is None
    assert "example_recipe_id" not in target


def test_discover_execution_target_ignores_hidden_dirs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    hidden_dir = workspace / ".hidden-tools" / "scripts"
    hidden_dir.mkdir(parents=True)
    (hidden_dir / "tooling.py").write_text("import mindspore\n", encoding="utf-8")
    hidden_other = workspace / ".agent-cache"
    hidden_other.mkdir(parents=True)
    (hidden_other / "helper.py").write_text("print('tooling only')\n", encoding="utf-8")

    target = discover_execution_target(workspace, _args())

    assert target["entry_script"] is None
    assert target["framework_candidate"] is None
    assert target["framework_evidence"] == []


def test_build_state_uses_workspace_pta_evidence_without_mindspore_probe(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train_qwen3.py").write_text(
        "import torch\nimport torch_npu\nfrom transformers import Trainer, TrainingArguments\nfrom datasets import load_dataset\n",
        encoding="utf-8",
    )
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="auto",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    target = state["target"]
    framework_layer = state["closure"]["layers"]["framework"]
    runtime_layer = state["closure"]["layers"]["runtime_dependencies"]

    assert target["target_type"] == "training"
    assert target["framework_candidate"] == "pta"
    assert framework_layer["required_packages"] == ["torch", "torch_npu"]
    assert "mindspore" not in framework_layer["required_packages"]
    assert "mindspore" not in (framework_layer.get("import_probes") or {})
    assert "mindspore" not in (runtime_layer.get("required_imports") or [])


def test_build_state_ignores_hidden_dirs_when_inferring_framework(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train_qwen3.py").write_text(
        "import torch\nimport torch_npu\nfrom transformers import Trainer\n",
        encoding="utf-8",
    )
    hidden_dir = workspace / ".hidden-tools" / "scripts"
    hidden_dir.mkdir(parents=True)
    (hidden_dir / "tooling.py").write_text("import mindspore\n", encoding="utf-8")
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="auto",
            framework_hint="auto",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    assert Path(state["target"]["entry_script"]).name == "train_qwen3.py"
    assert state["target"]["framework_candidate"] == "pta"
    assert state["target"]["framework_evidence"] == ["pta imports detected"]


def test_resolve_selected_python_uses_active_shell_env_when_workspace_env_missing(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    active_env = tmp_path / "conda-env"
    active_python = _workspace_python_path(active_env)
    monkeypatch.setenv("CONDA_PREFIX", str(active_env))
    monkeypatch.setattr(
        python_selection,
        "inspect_candidate",
        lambda root, python_path, source, env_root: python_selection._selection_result(
            root=root,
            python_path=python_path,
            env_root=env_root,
            source=source,
            status="selected",
            reason="selected python is usable for readiness-agent helpers",
            python_version="3.10.0",
            version_info=(3, 10, 0),
        ),
    )

    result = python_selection.resolve_selected_python(workspace)

    assert result["selection_status"] == "selected"
    assert result["selection_source"] == "active_shell_env"
    assert result["selected_env_root"] == str(active_env)
    assert result["selected_python"] == str(active_python)


def test_selected_python_for_execution_accepts_active_shell_env_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    active_env = tmp_path / "external-env"
    active_python = _workspace_python_path(active_env)

    closure = {
        "layers": {
            "python_environment": {
                "selection_source": "active_shell_env",
                "selected_env_root": str(active_env),
                "probe_python_path": str(active_python),
            }
        }
    }

    selected = selected_python_for_execution(workspace, {"selected_python": None}, closure)

    assert selected == active_python


def test_build_state_requires_framework_confirmation_when_hint_is_missing(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train_qwen3.py").write_text(
        "import torch\nimport torch_npu\nfrom transformers import Trainer\n",
        encoding="utf-8",
    )
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="training",
            framework_hint=None,
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    framework_blocker = next(item for item in state["checks"] if item["id"] == "framework-selection")
    framework_layer = state["closure"]["layers"]["framework"]

    assert state["target"]["framework_candidate"] == "pta"
    assert framework_blocker["status"] == "block"
    assert framework_blocker["confirmation_required"] is True
    assert any(option["framework"] == "pta" for option in framework_blocker["confirmation_options"])
    assert framework_layer["framework_path"] is None
    assert framework_layer["framework_candidate"] == "pta"
    assert framework_layer["confirmation_required"] is True
    assert not any(item["id"] == "framework-importability" for item in state["checks"])


def test_runtime_smoke_blocks_when_script_parse_prerequisites_are_missing(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("print('infer')\n", encoding="utf-8")
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="inference",
            framework_hint="auto",
            model_path="model",
        ),
        workspace,
    )

    runtime_smoke = next(item for item in state["checks"] if item["id"] == "runtime-smoke")
    assert runtime_smoke["status"] == "block"
    assert "prerequisites are unresolved" in runtime_smoke["summary"]


def test_build_fix_actions_creates_workspace_uv_env_before_installing_missing_packages(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external_env = tmp_path / "external-env"
    external_python = _workspace_python_path(external_env)
    monkeypatch.setattr(readiness_core, "resolve_uv_executable", lambda: None)

    target = {
        "working_dir": str(workspace),
        "framework_path": "pta",
    }
    closure = {
        "layers": {
            "python_environment": {
                "selection_status": "selected",
                "selected_env_root": str(external_env),
                "probe_python_path": str(external_python),
            },
            "framework": {
                "framework_path": "pta",
                "import_probes": {"torch": False, "torch_npu": False},
                "recommended_package_specs": ["torch==2.9.0", "torch_npu==2.9.0"],
            },
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }

    actions = _planned_actions(target, closure, {"blockers_detailed": []})
    action_types = [item["action_type"] for item in actions]

    assert "install_uv" in action_types
    assert "create_or_select_env" in action_types
    assert "install_framework_packages" not in action_types


def test_build_fix_actions_plans_uv_env_and_package_installs_when_workspace_env_is_missing(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(readiness_core, "resolve_uv_executable", lambda: None)

    target = {
        "working_dir": str(workspace),
        "framework_path": "pta",
    }
    closure = {
        "layers": {
            "python_environment": {
                "selection_status": "missing",
            },
            "framework": {
                "framework_path": "pta",
                "required_packages": ["torch", "torch_npu"],
                "recommended_package_specs": ["torch==2.9.0", "torch_npu==2.9.0"],
                "import_probes": {},
            },
            "runtime_dependencies": {
                "required_imports": ["datasets", "transformers"],
                "import_probes": {},
            },
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }

    actions = _planned_actions(target, closure, {"blockers_detailed": []})
    action_types = [item["action_type"] for item in actions]

    assert "install_uv" in action_types
    assert "create_or_select_env" in action_types
    assert "install_framework_packages" not in action_types
    assert "install_runtime_dependencies" not in action_types


def test_selected_python_for_execution_prefers_workspace_uv_env_over_external_selection(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_python = _workspace_python_path(workspace / ".venv")
    external_env = tmp_path / "external-env"
    external_python = _workspace_python_path(external_env)

    selected = selected_python_for_execution(
        workspace,
        {"selected_python": str(external_python)},
        {
            "layers": {
                "python_environment": {
                    "selected_env_root": str(external_env),
                    "probe_python_path": str(external_python),
                }
            }
        },
    )

    assert selected == workspace_python


def test_install_packages_uses_uv_pip_with_selected_python(tmp_path: Path, monkeypatch):
    python_path = _workspace_python_path(tmp_path / ".venv")
    uv_path = tmp_path / "uv"
    uv_path.write_text("", encoding="utf-8")
    commands = []

    monkeypatch.setattr(readiness_core, "ensure_uv_available", lambda: (True, "uv is already available", uv_path))
    monkeypatch.setattr(readiness_core, "preferred_pip_index_urls", lambda: ["https://mirror.example/simple"])

    def _record_command(command):
        commands.append(command)
        return True, ""

    monkeypatch.setattr(readiness_core, "run_install_command", _record_command)

    ok, message = install_packages(python_path, ["torch==2.9.0", "torch_npu==2.9.0"])

    assert ok is True
    assert "installed packages via https://mirror.example/simple" == message
    assert commands == [[
        str(uv_path),
        "pip",
        "install",
        "--python",
        str(python_path),
        "--index-url",
        "https://mirror.example/simple",
        "torch==2.9.0",
        "torch_npu==2.9.0",
    ]]


def test_build_fix_actions_adds_remote_downloads_when_remote_assets_exist(tmp_path: Path):
    env_root = tmp_path / ".venv"
    python_path = _workspace_python_path(env_root)
    target = {
        "working_dir": str(tmp_path),
    }
    closure = {
        "layers": {
            "python_environment": {
                "selection_status": "selected",
                "selected_env_root": str(env_root),
                "probe_python_path": str(python_path),
            },
            "framework": {"framework_path": None, "import_probes": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {
                "entry_script": {"exists": True},
                "model_path": {"satisfied": False},
                "dataset_path": {"satisfied": False},
            },
            "remote_assets": {
                "assets": {
                    "model_path": {"repo_id": "Qwen/Qwen3-0.6B", "local_path": str(tmp_path / "model")},
                    "dataset_path": {"repo_id": "repo", "split": "train", "local_path": str(tmp_path / "dataset")},
                }
            },
        }
    }
    actions = _planned_actions(target, closure, {"blockers_detailed": []})
    action_types = {item["action_type"] for item in actions}
    assert "download_model_asset" in action_types
    assert "download_dataset_asset" in action_types


def test_build_fix_actions_adds_example_scaffold_when_recipe_applies(tmp_path: Path):
    target = {
        "working_dir": str(tmp_path),
        "entry_script": str(tmp_path / "train.py"),
        "example_template_path": str((Path(__file__).resolve().parents[1] / "examples" / "qwen3_0_6b_training_example.py").resolve()),
    }
    closure = {
        "layers": {
            "python_environment": {"selection_status": "selected"},
            "framework": {"framework_path": None, "import_probes": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {
                "entry_script": {"exists": False},
                "model_path": {"satisfied": True},
                "dataset_path": {"satisfied": True},
            },
            "remote_assets": {"assets": {}},
        }
    }
    actions = _planned_actions(target, closure, {"blockers_detailed": []})
    assert any(item["action_type"] == "scaffold_example_entry" for item in actions)


def test_build_fix_actions_plans_workspace_cann_install_when_runtime_is_missing(tmp_path: Path):
    target = {
        "working_dir": str(tmp_path),
        "framework_path": "pta",
        "confirm_managed_cann": True,
    }
    closure = {
        "layers": {
            "system": {
                "requires_ascend": True,
                "cann_path_input": None,
                "ascend_env_script_present": False,
                "managed_cann_plan": {
                    "status": "installable",
                    "cann_version": "8.5.0",
                    "chip_type": "910b",
                    "artifacts": {
                        "status": "resolved",
                        "toolkit": {"status": "resolved", "file_name": "Ascend-cann-toolkit_8.5.0_linux-x86_64.run"},
                        "ops": {"status": "resolved", "file_name": "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run"},
                    },
                },
            },
            "python_environment": {"selection_status": "selected"},
            "framework": {"framework_path": "pta", "import_probes": {}, "installed_compatibility": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }

    actions = _planned_actions(target, closure, {"blockers_detailed": []})

    assert actions[0]["action_type"] == "install_workspace_cann"
    assert actions[0]["cann_version"] == "8.5.0"
    assert actions[0]["chip_type"] == "910b"
    assert len(actions) == 1


def test_build_fix_actions_returns_no_actions_when_managed_cann_install_needs_confirmation(tmp_path: Path):
    target = {
        "working_dir": str(tmp_path),
        "framework_path": "pta",
        "confirm_managed_cann": False,
    }
    closure = {
        "layers": {
            "system": {
                "requires_ascend": True,
                "cann_path_input": None,
                "ascend_env_script_present": False,
                "managed_cann_plan": {
                    "status": "installable",
                    "cann_version": "8.5.0",
                    "chip_type": "910b",
                    "artifacts": {
                        "status": "resolved",
                        "toolkit": {"status": "resolved", "file_name": "Ascend-cann-toolkit_8.5.0_linux-x86_64.run"},
                        "ops": {"status": "resolved", "file_name": "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run"},
                    },
                },
            },
            "python_environment": {"selection_status": "selected"},
            "framework": {"framework_path": "pta", "import_probes": {}, "installed_compatibility": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }
    normalized = {
        "blockers_detailed": [
            {
                "id": "cann-runtime",
                "summary": "Readiness can install a compatible managed workspace-local CANN, but needs your confirmation before doing so.",
                "confirmation_required": True,
                "remediable": True,
                "remediation_owner": "readiness-agent",
                "revalidation_scope": ["framework", "runtime-smoke"],
            }
        ]
    }

    actions = _planned_actions(target, closure, normalized)

    assert actions == []


def test_build_fix_actions_returns_no_actions_for_invalid_explicit_cann_blocker(tmp_path: Path):
    target = {
        "working_dir": str(tmp_path),
        "framework_path": "pta",
    }
    closure = {
        "layers": {
            "system": {
                "cann_path_input": str(tmp_path / "broken-cann"),
            },
            "python_environment": {"selection_status": "selected"},
            "framework": {"framework_path": "pta", "import_probes": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }
    normalized = {
        "blockers_detailed": [
            {
                "id": "cann-runtime",
                "summary": "The explicit cann_path could not be resolved to a usable set_env.sh.",
                "evidence": [f"cann_path={tmp_path / 'broken-cann'}"],
                "remediable": False,
            }
        ]
    }

    actions = _planned_actions(target, closure, normalized)

    assert actions == []


def test_build_fix_actions_returns_no_actions_for_invalid_explicit_ascend_env_input(tmp_path: Path):
    target = {
        "working_dir": str(tmp_path),
        "framework_path": "pta",
    }
    closure = {
        "layers": {
            "system": {
                "ascend_env_input_present": True,
                "ascend_env_input_vars": ["ASCEND_HOME_PATH"],
                "ascend_env_input_values": {"ASCEND_HOME_PATH": str(tmp_path / "broken-ascend")},
            },
            "python_environment": {"selection_status": "selected"},
            "framework": {"framework_path": "pta", "import_probes": {}},
            "runtime_dependencies": {"import_probes": {}},
            "workspace_assets": {"entry_script": {"exists": True}},
            "remote_assets": {"assets": {}},
        }
    }
    normalized = {
        "blockers_detailed": [
            {
                "id": "cann-runtime",
                "summary": "The explicit Ascend environment variables could not be resolved to a usable set_env.sh.",
                "evidence": [f"ASCEND_HOME_PATH={tmp_path / 'broken-ascend'}"],
                "remediable": False,
            }
        ]
    }

    actions = _planned_actions(target, closure, normalized)

    assert actions == []


def test_build_state_prefers_explicit_cann_path_over_managed_workspace(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()
    explicit_cann = _make_fake_cann_dir(tmp_path / "explicit-cann", version="8.5.0")
    _make_fake_cann_dir(workspace / "cann" / "8.3.RC1", version="8.3.RC1")

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
            cann_path=str(explicit_cann),
        ),
        workspace,
    )

    system_layer = state["closure"]["layers"]["system"]
    assert system_layer["selected_cann_source"] == "explicit_input"
    assert str(explicit_cann) in system_layer["selected_cann_path"]


def test_detect_cann_version_reads_metadef_version_info_before_falling_back_to_path_token(tmp_path: Path):
    cann_root = tmp_path / "cann-8.5.0-bak"
    script_path = cann_root / "ascend-toolkit" / "set_env.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    version_info = cann_root / "ascend-toolkit" / "latest" / "share" / "info" / "metadef" / "version.info"
    version_info.parent.mkdir(parents=True, exist_ok=True)
    version_info.write_text("Version=25.5.0\n", encoding="utf-8")

    detected = detect_cann_version(script_path=str(script_path))

    assert detected["cann_version"] == "25.5.0"
    assert str(version_info) == detected["cann_version_file"]


def test_build_state_reuses_managed_workspace_cann_before_other_candidates(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()
    _make_fake_cann_dir(workspace / "cann" / "8.5.0", version="8.5.0")

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    system_layer = state["closure"]["layers"]["system"]
    assert system_layer["selected_cann_source"] == "managed_workspace"
    assert str(workspace / "cann") in str(system_layer["selected_cann_path"])


def test_build_state_requires_confirmation_before_using_bounded_search_cann(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()
    home_root = tmp_path / "home"
    home_root.mkdir()
    candidate_root = _make_fake_cann_dir(home_root / "cann-8.5.0", version="8.5.0")
    monkeypatch.setenv("HOME", str(home_root))

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    system_layer = state["closure"]["layers"]["system"]
    blocker = next(item for item in state["normalized"]["blockers_detailed"] if item["id"] == "cann-runtime")
    assert system_layer["selected_cann_source"] == "bounded_search"
    assert str(candidate_root) in str(system_layer["selected_cann_path"])
    assert blocker["confirmation_required"] is True
    assert any(option["kind"] == "existing_cann" for option in blocker["confirmation_options"])


def test_build_state_prefers_explicit_ascend_env_input_over_managed_workspace(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()
    explicit_env_cann = _make_fake_cann_dir(tmp_path / "env-cann", version="8.5.0")
    _make_fake_cann_dir(workspace / "cann" / "8.3.RC1", version="8.3.RC1")
    monkeypatch.setenv("ASCEND_HOME_PATH", str((explicit_env_cann / "ascend-toolkit").resolve()))

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    system_layer = state["closure"]["layers"]["system"]
    assert system_layer["selected_cann_source"] == "env_input"
    assert str(explicit_env_cann) in system_layer["selected_cann_path"]


def test_build_state_blocks_when_explicit_ascend_env_input_is_invalid(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()
    monkeypatch.setenv("ASCEND_HOME_PATH", str((tmp_path / "broken-ascend").resolve()))

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    blocker = next(item for item in state["checks"] if item["id"] == "cann-runtime")
    assert blocker["status"] == "block"
    assert blocker["remediable"] is False
    assert "explicit Ascend environment variables" in blocker["summary"]


def test_build_state_marks_missing_cann_as_remediable_blocker_on_supported_host(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    _set_supported_linux_host(monkeypatch)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()

    artifact_dir = (workspace / ".readiness" / "artifacts" / "cann").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    toolkit_path = artifact_dir / "Ascend-cann-toolkit_8.5.0_linux-x86_64.run"
    ops_path = artifact_dir / "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run"
    toolkit_path.write_bytes(b"toolkit")
    ops_path.write_bytes(b"ops")
    monkeypatch.setenv("READINESS_CANN_TOOLKIT_SHA256_TOOLKIT_X86_64_8_5_0", hashlib.sha256(toolkit_path.read_bytes()).hexdigest())
    monkeypatch.setenv("READINESS_CANN_OPS_SHA256_OPS_X86_64_8_5_0_910B", hashlib.sha256(ops_path.read_bytes()).hexdigest())

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    blocker = next(item for item in state["checks"] if item["id"] == "cann-runtime")
    assert blocker["status"] == "block"
    assert blocker["remediable"] is True


class _FakeUrlopenResponse:
    def __init__(self, body: bytes = b"", headers: dict | None = None):
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_resolve_cann_artifacts_use_official_hiascend_api_and_encode_obs_urls(tmp_path: Path, monkeypatch):
    api_url = "https://www.hiascend.com/ascendgateway/ascendservice/cann/info/zh/0?versionName=8.5.0"
    raw_toolkit_download_url = (
        "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/"
        "Ascend-cann-toolkit_8.5.0_linux-x86_64.run"
    )
    raw_ops_download_url = (
        "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/"
        "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run"
    )
    encoded_toolkit_download_url = raw_toolkit_download_url.replace("CANN 8.5.0", "CANN%208.5.0")
    encoded_ops_download_url = raw_ops_download_url.replace("CANN 8.5.0", "CANN%208.5.0")

    def _fake_urlopen(request, timeout=0):
        url = request.full_url
        method = request.get_method()
        if method == "GET" and url == api_url:
            body = (
                b'{"code":200,"msg":"success","data":{"packageList":['
                b'{"softwareName":"Ascend-cann-toolkit_8.5.0_linux-x86_64.run",'
                b'"downloadUrl":"https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-toolkit_8.5.0_linux-x86_64.run",'
                b'"digitalSignatureUrl":"https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-toolkit_8.5.0_linux-x86_64.run.asc",'
                b'"cpuName":"X86_64","packageType":"run","softwarePackageType":0},'
                b'{"softwareName":"Ascend-cann-910b-ops_8.5.0_linux-x86_64.run",'
                b'"downloadUrl":"https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-910b-ops_8.5.0_linux-x86_64.run",'
                b'"digitalSignatureUrl":"https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-910b-ops_8.5.0_linux-x86_64.run.asc",'
                b'"cpuName":"X86_64","packageType":"run","softwarePackageType":0}]}}'
            )
            return _FakeUrlopenResponse(body=body)
        if method == "HEAD" and url == encoded_toolkit_download_url:
            return _FakeUrlopenResponse(headers={"ETag": '"13c14c7179864e70989cc0d1707b543a"'})
        if method == "HEAD" and url == encoded_ops_download_url:
            return _FakeUrlopenResponse(headers={"ETag": '"2ec565b62ddad0b5608724484378cc79"'})
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(managed_cann, "urlopen", _fake_urlopen)

    ignored_global_root = tmp_path / "global-cache"
    ignored_global_root.mkdir()
    (ignored_global_root / "Ascend-cann-toolkit_8.5.0_linux-x86_64.run").write_bytes(b"local-toolkit")
    (ignored_global_root / "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run").write_bytes(b"local-ops")

    artifacts = managed_cann.resolve_cann_artifacts(
        tmp_path,
        "x86_64",
        "8.5.0",
        "910b",
        environ={
            "READINESS_CANN_ARTIFACT_ROOT": str(ignored_global_root),
            "READINESS_CANN_ARTIFACT_BASE_URL": "https://mirror.example.invalid/cann",
        },
    )

    assert artifacts["status"] == "resolved"
    assert artifacts["toolkit"]["file_name"] == "Ascend-cann-toolkit_8.5.0_linux-x86_64.run"
    assert artifacts["toolkit"]["source_url"] == encoded_toolkit_download_url
    assert artifacts["toolkit"]["checksum_kind"] == "md5"
    assert artifacts["toolkit"]["checksum"] == "13c14c7179864e70989cc0d1707b543a"
    assert artifacts["toolkit"]["signature_urls"] == [
        "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-toolkit_8.5.0_linux-x86_64.run.asc"
    ]
    assert artifacts["ops"]["file_name"] == "Ascend-cann-910b-ops_8.5.0_linux-x86_64.run"
    assert artifacts["ops"]["source_url"] == encoded_ops_download_url
    assert artifacts["ops"]["checksum_kind"] == "md5"
    assert artifacts["ops"]["checksum"] == "2ec565b62ddad0b5608724484378cc79"
    assert artifacts["ops"]["signature_urls"] == [
        "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN 8.5.0/Ascend-cann-910b-ops_8.5.0_linux-x86_64.run.asc"
    ]
    assert "mirror.example.invalid" not in artifacts["toolkit"]["source_url"]
    assert artifacts["toolkit"]["source_path"] is None


def test_build_state_blocks_with_clear_cann_reason_on_unsupported_host(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "darwin")
    monkeypatch.setenv("READINESS_HOST_ARCH", "x86_64")
    monkeypatch.delenv("READINESS_DRIVER_VERSION", raising=False)
    monkeypatch.delenv("READINESS_FIRMWARE_VERSION", raising=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    blocker = next(item for item in state["checks"] if item["id"] == "cann-runtime")
    assert blocker["status"] == "block"
    assert blocker["remediable"] is False
    assert "does not support managed workspace-local CANN" in blocker["summary"]


def test_build_state_blocks_with_clear_cann_reason_when_driver_version_is_unresolved(tmp_path: Path, fake_selected_python: Path, monkeypatch):
    monkeypatch.setenv("READINESS_HOST_PLATFORM", "linux")
    monkeypatch.setenv("READINESS_HOST_ARCH", "x86_64")
    monkeypatch.delenv("READINESS_DRIVER_VERSION", raising=False)
    monkeypatch.setenv("READINESS_FIRMWARE_VERSION", "7.3.0")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "infer.py").write_text("import torch\nimport torch_npu\n", encoding="utf-8")
    (workspace / "model").mkdir()

    state = build_state(
        _args(
            target="inference",
            framework_hint="pta",
            selected_python=str(fake_selected_python),
            model_path="model",
        ),
        workspace,
    )

    blocker = next(item for item in state["checks"] if item["id"] == "cann-runtime")
    assert blocker["status"] == "block"
    assert blocker["remediable"] is False
    assert "could not determine the host driver version" in blocker["summary"]


def test_probe_hf_endpoint_retries_and_falls_back_to_api_probe():
    _RetryProbeHandler.api_attempts = 0
    with socketserver.TCPServer(("127.0.0.1", 0), _RetryProbeHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        reachable, error = probe_hf_endpoint(endpoint)
        server.shutdown()
        thread.join(timeout=2)

    assert reachable is True
    assert error is None
    assert _RetryProbeHandler.api_attempts == 3
