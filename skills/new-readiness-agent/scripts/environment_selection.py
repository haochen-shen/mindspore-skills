#!/usr/bin/env python3
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


WORKSPACE_ENV_CANDIDATES = (
    ".venv",
    "venv",
    ".env",
    "env",
)
PYTHON_RELATIVE_CANDIDATES = (
    Path("bin/python"),
    Path("bin/python3"),
    Path("Scripts/python.exe"),
    Path("Scripts/python"),
)
MIN_RUNTIME_PROBE_PYTHON = (3, 8)


def resolve_optional_path(value: Optional[str], root: Path) -> Optional[Path]:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def python_in_env(env_root: Path) -> Optional[Path]:
    for candidate in PYTHON_RELATIVE_CANDIDATES:
        python_path = env_root / candidate
        if python_path.exists() and python_path.is_file():
            return python_path
    return None


def derive_env_root_from_python(python_path: Path) -> Optional[Path]:
    parent_name = python_path.parent.name.lower()
    if parent_name in {"bin", "scripts"}:
        return python_path.parent.parent
    return None


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    return True


def inspect_python(python_path: Path) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    command = [
        str(python_path),
        "-c",
        (
            "import json, platform, sys; "
            "print(json.dumps({"
            "'version_info': list(sys.version_info[:3]), "
            "'version': platform.python_version(), "
            "'executable': sys.executable"
            "}))"
        ),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)

    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None, "python probe returned non-JSON output"
    if not isinstance(payload, dict):
        return None, "python probe returned a non-object payload"
    return payload, None


def split_command(command: Optional[str]) -> List[str]:
    if not command:
        return []
    for posix_mode in (os.name != "nt", True, False):
        try:
            return shlex.split(command, posix=posix_mode)
        except ValueError:
            continue
    return [item for item in str(command).strip().split() if item]


def conda_executable() -> Optional[str]:
    for token in ("conda", "mamba"):
        resolved = shutil.which(token)
        if resolved:
            return resolved
    return None


def resolve_conda_name_to_prefix(name: str) -> Optional[Path]:
    executable = conda_executable()
    if not executable:
        return None
    try:
        completed = subprocess.run(
            [executable, "env", "list", "--json"],
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return None
    envs = payload.get("envs")
    if not isinstance(envs, list):
        return None
    for item in envs:
        candidate = Path(str(item))
        if candidate.name == name:
            return candidate
    return None


def _candidate(
    *,
    kind: str,
    selection_source: str,
    label: str,
    root: Path,
    python_path: Optional[Path] = None,
    env_root: Optional[Path] = None,
    env_name: Optional[str] = None,
    is_active: bool = False,
    matches_launch_command: bool = False,
    recommended_reason: Optional[str] = None,
) -> Dict[str, object]:
    candidate: Dict[str, object] = {
        "kind": kind,
        "selection_source": selection_source,
        "label": label,
        "python_path": str(python_path) if python_path else None,
        "env_root": str(env_root) if env_root else None,
        "env_name": env_name,
        "is_active": is_active,
        "matches_launch_command": matches_launch_command,
        "workspace_local": bool(env_root and path_is_within(env_root, root)),
        "recommended_reason": recommended_reason,
    }
    return candidate


def _inspect_candidate(root: Path, candidate: Dict[str, object]) -> Dict[str, object]:
    python_path_value = candidate.get("python_path")
    env_root_value = candidate.get("env_root")
    python_path = Path(str(python_path_value)) if python_path_value else None
    env_root = Path(str(env_root_value)) if env_root_value else None

    if not python_path and env_root:
        env_python = python_in_env(env_root)
        if env_python:
            python_path = env_python
            candidate["python_path"] = str(env_python)

    if not python_path:
        candidate["status"] = "unresolved"
        candidate["reason"] = "candidate environment does not expose a Python executable"
        candidate["confidence"] = 0.2
        return candidate

    payload, error = inspect_python(python_path)
    if error:
        candidate["status"] = "invalid"
        candidate["reason"] = error
        candidate["confidence"] = 0.1
        return candidate

    version_info_raw = payload.get("version_info") or []
    version_info: Optional[Tuple[int, int, int]] = None
    if isinstance(version_info_raw, list) and len(version_info_raw) >= 3:
        try:
            version_info = (
                int(version_info_raw[0]),
                int(version_info_raw[1]),
                int(version_info_raw[2]),
            )
        except (TypeError, ValueError):
            version_info = None

    candidate["python_version"] = payload.get("version")
    candidate["python_version_info"] = list(version_info) if version_info else None
    candidate["control_python_same_as_runtime"] = str(payload.get("executable")) == sys.executable

    if not version_info:
        candidate["status"] = "invalid"
        candidate["reason"] = "python probe did not return a usable version"
        candidate["confidence"] = 0.1
        return candidate

    if version_info < MIN_RUNTIME_PROBE_PYTHON:
        candidate["status"] = "unsupported"
        candidate["reason"] = "python is below the minimum supported runtime probe version 3.8"
        candidate["confidence"] = 0.15
        return candidate

    candidate["status"] = "selected"
    candidate["reason"] = "python is available for near-launch readiness probes"
    candidate["confidence"] = 0.4
    return candidate


def _boost_confidence(candidate: Dict[str, object], launch_detected: bool, root: Path) -> None:
    confidence = float(candidate.get("confidence") or 0.0)
    if candidate.get("matches_launch_command"):
        confidence += 0.35
    if candidate.get("is_active"):
        confidence += 0.2
    if candidate.get("workspace_local"):
        confidence += 0.15
    if candidate.get("kind") == "system-python":
        confidence -= 0.1
    if candidate.get("kind") in {"explicit_python", "explicit_env"}:
        confidence += 0.35
    if candidate.get("kind") == "uv-project":
        confidence += 0.1
    if candidate.get("env_root"):
        env_root = Path(str(candidate["env_root"]))
        if path_is_within(env_root, root):
            confidence += 0.05
    if not launch_detected:
        confidence -= 0.05
    candidate["confidence"] = round(max(0.0, min(confidence, 0.99)), 2)


def _dedupe_candidates(candidates: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    unique: List[Dict[str, object]] = []
    for candidate in candidates:
        key = (
            candidate.get("kind"),
            candidate.get("python_path"),
            candidate.get("env_root"),
            candidate.get("env_name"),
            candidate.get("label"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _workspace_env_candidates(root: Path) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    uv_enabled = (root / "uv.lock").exists()
    for candidate_name in WORKSPACE_ENV_CANDIDATES:
        env_root = root / candidate_name
        if not env_root.exists():
            continue
        kind = "uv-project" if uv_enabled and candidate_name == ".venv" else "workspace-env"
        label = f"{candidate_name} ({kind})"
        results.append(
            _candidate(
                kind=kind,
                selection_source="workspace_scan",
                label=label,
                root=root,
                env_root=env_root,
                recommended_reason="workspace-local environment discovered",
            )
        )
    if uv_enabled and not any(item.get("kind") == "uv-project" for item in results):
        results.append(
            _candidate(
                kind="uv-project",
                selection_source="workspace_scan",
                label="uv project environment",
                root=root,
                env_root=root / ".venv",
                recommended_reason="uv.lock suggests a project-local environment",
            )
        )
    return results


def _active_env_candidates(root: Path) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        env_root = Path(virtual_env)
        results.append(
            _candidate(
                kind="active-venv",
                selection_source="current_environment",
                label="current active virtualenv",
                root=root,
                env_root=env_root,
                is_active=True,
                recommended_reason="current shell is already inside this virtual environment",
            )
        )

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        env_root = Path(conda_prefix)
        results.append(
            _candidate(
                kind="active-conda",
                selection_source="current_environment",
                label="current active conda environment",
                root=root,
                env_root=env_root,
                is_active=True,
                recommended_reason="current shell is already inside this conda environment",
            )
        )
    return results


def _explicit_candidates(root: Path, selected_python: Optional[str], selected_env_root: Optional[str]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    explicit_python = resolve_optional_path(selected_python, root)
    if explicit_python:
        results.append(
            _candidate(
                kind="explicit_python",
                selection_source="explicit_input",
                label="explicit selected_python",
                root=root,
                python_path=explicit_python,
                env_root=derive_env_root_from_python(explicit_python),
                matches_launch_command=True,
                recommended_reason="user explicitly provided selected_python",
            )
        )
    explicit_env = resolve_optional_path(selected_env_root, root)
    if explicit_env:
        results.append(
            _candidate(
                kind="explicit_env",
                selection_source="explicit_input",
                label="explicit selected_env_root",
                root=root,
                env_root=explicit_env,
                matches_launch_command=True,
                recommended_reason="user explicitly provided selected_env_root",
            )
        )
    return results


def _system_python_candidates(root: Path) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    seen = set()
    for token in (sys.executable, shutil.which("python"), shutil.which("python3")):
        if not token:
            continue
        path = Path(str(token))
        normalized = str(path.resolve()) if path.exists() else str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        results.append(
            _candidate(
                kind="system-python",
                selection_source="host_environment",
                label=f"system python: {path.name}",
                root=root,
                python_path=path,
                env_root=derive_env_root_from_python(path),
                recommended_reason="host python detected from the current machine",
            )
        )
    return results


def _launch_command_candidates(root: Path, launch_command: Optional[str]) -> List[Dict[str, object]]:
    tokens = split_command(launch_command)
    if not tokens:
        return []

    results: List[Dict[str, object]] = []

    if len(tokens) >= 2 and tokens[0] == "uv" and tokens[1] == "run":
        results.append(
            _candidate(
                kind="launch-uv",
                selection_source="launch_command",
                label="launch command uses uv run",
                root=root,
                env_root=root / ".venv",
                matches_launch_command=True,
                recommended_reason="launch command explicitly uses uv run",
            )
        )

    if len(tokens) >= 2 and tokens[0] == "conda" and tokens[1] == "run":
        for index, token in enumerate(tokens[:-1]):
            if token in {"-p", "--prefix"} and index + 1 < len(tokens):
                env_root = resolve_optional_path(tokens[index + 1], root)
                results.append(
                    _candidate(
                        kind="launch-conda-prefix",
                        selection_source="launch_command",
                        label="launch command uses conda --prefix",
                        root=root,
                        env_root=env_root,
                        matches_launch_command=True,
                        recommended_reason="launch command explicitly uses conda --prefix",
                    )
                )
                break
            if token in {"-n", "--name"} and index + 1 < len(tokens):
                env_name = tokens[index + 1]
                env_root = resolve_conda_name_to_prefix(env_name)
                results.append(
                    _candidate(
                        kind="launch-conda-name",
                        selection_source="launch_command",
                        label=f"launch command uses conda env {env_name}",
                        root=root,
                        env_root=env_root,
                        env_name=env_name,
                        matches_launch_command=True,
                        recommended_reason="launch command explicitly uses conda run",
                    )
                )
                break

    for token in tokens:
        lowered = token.lower()
        if lowered.endswith("python") or lowered.endswith("python.exe") or lowered in {"python", "python3", "py"}:
            if lowered in {"python", "python3", "py"}:
                continue
            python_path = resolve_optional_path(token, root)
            if python_path:
                results.append(
                    _candidate(
                        kind="launch-python",
                        selection_source="launch_command",
                        label="launch command explicitly references a Python executable",
                        root=root,
                        python_path=python_path,
                        env_root=derive_env_root_from_python(python_path),
                        matches_launch_command=True,
                        recommended_reason="launch command explicitly references this Python executable",
                    )
                )
                break
    return results


def build_environment_candidates(
    root: Path,
    *,
    launch_command: Optional[str],
    selected_python: Optional[str],
    selected_env_root: Optional[str],
) -> Dict[str, object]:
    candidates = []
    candidates.extend(_explicit_candidates(root, selected_python, selected_env_root))
    candidates.extend(_launch_command_candidates(root, launch_command))
    candidates.extend(_active_env_candidates(root))
    candidates.extend(_workspace_env_candidates(root))
    candidates.extend(_system_python_candidates(root))
    candidates = _dedupe_candidates(candidates)

    launch_detected = bool(split_command(launch_command))
    inspected: List[Dict[str, object]] = []
    for index, candidate in enumerate(candidates, start=1):
        candidate["id"] = f"env-{index}"
        inspected_candidate = _inspect_candidate(root, candidate)
        _boost_confidence(inspected_candidate, launch_detected, root)
        inspected.append(inspected_candidate)

    inspected.sort(
        key=lambda item: (
            float(item.get("confidence") or 0.0),
            1 if item.get("status") == "selected" else 0,
            1 if item.get("matches_launch_command") else 0,
            1 if item.get("is_active") else 0,
            1 if item.get("workspace_local") else 0,
        ),
        reverse=True,
    )

    if inspected:
        inspected[0]["recommended"] = True

    return {
        "candidates": inspected,
        "recommended_id": inspected[0]["id"] if inspected else None,
    }
