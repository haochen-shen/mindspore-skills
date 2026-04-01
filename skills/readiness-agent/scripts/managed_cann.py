#!/usr/bin/env python3
import hashlib
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from urllib.request import urlopen

from ascend_compat import normalize_cann_version


SUPPORTED_MANAGED_CANN_ARCHES = {"x86_64", "aarch64"}
HOST_COMPATIBILITY_ROWS = [
    {"arch": "x86_64", "driver_prefix": "24.1", "firmware_prefix": "7.3", "cann": "8.5.0"},
    {"arch": "aarch64", "driver_prefix": "24.1", "firmware_prefix": "7.3", "cann": "8.5.0"},
    {"arch": "x86_64", "driver_prefix": "24.0", "firmware_prefix": "7.2", "cann": "8.3.RC1"},
    {"arch": "aarch64", "driver_prefix": "24.0", "firmware_prefix": "7.2", "cann": "8.3.RC1"},
    {"arch": "x86_64", "driver_prefix": "23.1", "firmware_prefix": "7.1", "cann": "8.2.RC1"},
    {"arch": "aarch64", "driver_prefix": "23.1", "firmware_prefix": "7.1", "cann": "8.2.RC1"},
    {"arch": "x86_64", "driver_prefix": "23.0", "firmware_prefix": "7.0", "cann": "8.1.RC1"},
    {"arch": "aarch64", "driver_prefix": "23.0", "firmware_prefix": "7.0", "cann": "8.1.RC1"},
]
ARTIFACT_ROWS = [
    {"arch": "x86_64", "cann": "8.5.0", "file_name": "cann-8.5.0-linux-x86_64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "aarch64", "cann": "8.5.0", "file_name": "cann-8.5.0-linux-aarch64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "x86_64", "cann": "8.3.RC1", "file_name": "cann-8.3.RC1-linux-x86_64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "aarch64", "cann": "8.3.RC1", "file_name": "cann-8.3.RC1-linux-aarch64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "x86_64", "cann": "8.2.RC1", "file_name": "cann-8.2.RC1-linux-x86_64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "aarch64", "cann": "8.2.RC1", "file_name": "cann-8.2.RC1-linux-aarch64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "x86_64", "cann": "8.1.RC1", "file_name": "cann-8.1.RC1-linux-x86_64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
    {"arch": "aarch64", "cann": "8.1.RC1", "file_name": "cann-8.1.RC1-linux-aarch64.zip", "set_env_relpath": "ascend-toolkit/set_env.sh"},
]
VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)+(?:\.RC\d+)?)", re.IGNORECASE)
DRIVER_PATTERNS = (
    re.compile(r"driver(?:\s+version)?\s*[:=]\s*([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
    re.compile(r"driver\s+([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
)
FIRMWARE_PATTERNS = (
    re.compile(r"firmware(?:\s+version)?\s*[:=]\s*([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
    re.compile(r"firmware\s+([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
)


def normalize_arch(value: Optional[str]) -> Optional[str]:
    token = (value or "").strip().lower()
    if token in {"x86_64", "amd64"}:
        return "x86_64"
    if token in {"aarch64", "arm64"}:
        return "aarch64"
    return token or None


def managed_cann_root(working_dir: Path) -> Path:
    return (working_dir / ".readiness" / "cann").resolve()


def version_sort_key(value: Optional[str]) -> Tuple[int, int, int, int, int]:
    normalized = normalize_cann_version(value) or "0.0.0"
    if ".RC" in normalized:
        base, _, rc_token = normalized.partition(".RC")
        stable_flag = 0
        rc_value = int(re.sub(r"\D", "", rc_token) or "0")
    else:
        base = normalized
        stable_flag = 1
        rc_value = 999
    parts = [int(item) for item in base.split(".") if item.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2], stable_flag, rc_value)


def _read_command_output(command: List[str], timeout_seconds: int = 10) -> Optional[str]:
    try:
        completed = subprocess.run(command, check=True, text=True, capture_output=True, timeout=timeout_seconds)
    except (OSError, subprocess.SubprocessError):
        return None
    return (completed.stdout or completed.stderr or "").strip() or None


def _parse_version_with_patterns(text: Optional[str], patterns: Tuple[re.Pattern, ...]) -> Optional[str]:
    if not text:
        return None
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            token = match.group(1).strip()
            version_match = VERSION_PATTERN.search(token)
            if version_match:
                return version_match.group(1)
            return token
    version_match = VERSION_PATTERN.search(text)
    if version_match:
        return version_match.group(1)
    return None


def detect_host_facts(environ: Optional[Dict[str, str]] = None) -> dict:
    env = environ or os.environ
    platform_name = (env.get("READINESS_HOST_PLATFORM") or platform.system()).strip().lower()
    arch = normalize_arch(env.get("READINESS_HOST_ARCH") or platform.machine())
    driver_version = env.get("READINESS_DRIVER_VERSION")
    firmware_version = env.get("READINESS_FIRMWARE_VERSION")
    probe_source: List[str] = []

    if env.get("READINESS_HOST_PLATFORM"):
        probe_source.append("env:READINESS_HOST_PLATFORM")
    else:
        probe_source.append("platform.system")
    if env.get("READINESS_HOST_ARCH"):
        probe_source.append("env:READINESS_HOST_ARCH")
    else:
        probe_source.append("platform.machine")
    if env.get("READINESS_DRIVER_VERSION"):
        probe_source.append("env:READINESS_DRIVER_VERSION")
    if env.get("READINESS_FIRMWARE_VERSION"):
        probe_source.append("env:READINESS_FIRMWARE_VERSION")

    npu_smi_output = None
    if not driver_version or not firmware_version:
        npu_smi_output = _read_command_output(["npu-smi", "info"])
        if npu_smi_output:
            if not driver_version:
                driver_version = _parse_version_with_patterns(npu_smi_output, DRIVER_PATTERNS)
                if driver_version:
                    probe_source.append("npu-smi:driver")
            if not firmware_version:
                firmware_version = _parse_version_with_patterns(npu_smi_output, FIRMWARE_PATTERNS)
                if firmware_version:
                    probe_source.append("npu-smi:firmware")

    supported_managed_cann = platform_name == "linux" and arch in SUPPORTED_MANAGED_CANN_ARCHES
    return {
        "host_platform": platform_name,
        "host_arch": arch,
        "driver_version": driver_version,
        "firmware_version": firmware_version,
        "supported_managed_cann": supported_managed_cann,
        "host_probe_source": probe_source,
        "host_probe_error": None if npu_smi_output or supported_managed_cann or env else None,
    }


def select_latest_compatible_cann(host_facts: dict) -> dict:
    arch = host_facts.get("host_arch")
    driver_version = host_facts.get("driver_version")
    firmware_version = host_facts.get("firmware_version")
    payload = {
        "status": "unresolved",
        "cann_version": None,
        "reason": None,
        "compatible_rows": [],
    }

    if not host_facts.get("supported_managed_cann"):
        payload["status"] = "unsupported_host"
        payload["reason"] = "Managed workspace-local CANN is only supported on Linux x86_64 and aarch64 hosts."
        return payload
    if not driver_version:
        payload["status"] = "driver_version_unknown"
        payload["reason"] = "Driver version is unresolved, so readiness cannot choose a compatible CANN package."
        return payload
    if not firmware_version:
        payload["status"] = "firmware_version_unknown"
        payload["reason"] = "Firmware version is unresolved, so readiness cannot choose a compatible CANN package."
        return payload

    compatible_rows = [
        row
        for row in HOST_COMPATIBILITY_ROWS
        if row["arch"] == arch
        and str(driver_version).startswith(row["driver_prefix"])
        and str(firmware_version).startswith(row["firmware_prefix"])
    ]
    if not compatible_rows:
        payload["status"] = "unmapped_host"
        payload["reason"] = (
            f"No managed CANN mapping is available for arch={arch}, driver={driver_version}, firmware={firmware_version}."
        )
        return payload

    compatible_rows = sorted(compatible_rows, key=lambda row: version_sort_key(row["cann"]), reverse=True)
    payload["status"] = "resolved"
    payload["compatible_rows"] = compatible_rows
    payload["cann_version"] = compatible_rows[0]["cann"]
    payload["reason"] = (
        f"Selected the latest compatible managed CANN {compatible_rows[0]['cann']} for arch={arch}, "
        f"driver={driver_version}, firmware={firmware_version}."
    )
    return payload


def artifact_env_token(arch: str, cann_version: str) -> str:
    normalized_version = normalize_cann_version(cann_version) or cann_version
    token = f"{arch}_{normalized_version}".upper().replace(".", "_").replace("-", "_")
    return token


def resolve_cann_artifact(working_dir: Path, arch: Optional[str], cann_version: Optional[str], environ: Optional[Dict[str, str]] = None) -> dict:
    env = environ or os.environ
    payload = {
        "status": "unresolved",
        "reason": None,
        "file_name": None,
        "set_env_relpath": None,
        "source_path": None,
        "source_url": None,
        "checksum": None,
        "checksum_source": None,
    }
    if not arch or not cann_version:
        payload["reason"] = "Managed CANN artifact lookup requires both arch and cann_version."
        return payload

    row = next((item for item in ARTIFACT_ROWS if item["arch"] == arch and item["cann"] == cann_version), None)
    if not row:
        payload["reason"] = f"No managed CANN artifact mapping is available for arch={arch}, cann_version={cann_version}."
        return payload

    token = artifact_env_token(arch, cann_version)
    payload["file_name"] = row["file_name"]
    payload["set_env_relpath"] = row["set_env_relpath"]

    checksum = env.get(f"READINESS_CANN_SHA256_{token}") or row.get("sha256")
    if checksum:
        payload["checksum"] = checksum
        payload["checksum_source"] = f"env:READINESS_CANN_SHA256_{token}" if env.get(f"READINESS_CANN_SHA256_{token}") else "table"

    direct_url = env.get(f"READINESS_CANN_ARTIFACT_URL_{token}")
    if direct_url:
        payload["source_url"] = direct_url
        payload["status"] = "resolved" if checksum else "checksum_missing"
        payload["reason"] = None if checksum else f"Artifact {row['file_name']} is configured, but its checksum is unresolved."
        return payload

    local_cache_path = (working_dir / ".readiness" / "artifacts" / "cann" / row["file_name"]).resolve()
    if local_cache_path.exists():
        payload["source_path"] = str(local_cache_path)
        payload["status"] = "resolved" if checksum else "checksum_missing"
        payload["reason"] = None if checksum else f"Artifact {row['file_name']} is available locally, but its checksum is unresolved."
        return payload

    artifact_root = env.get("READINESS_CANN_ARTIFACT_ROOT")
    if artifact_root:
        root_path = Path(artifact_root).expanduser()
        if root_path.exists():
            candidate = root_path / row["file_name"] if root_path.is_dir() else root_path
            if candidate.exists():
                payload["source_path"] = str(candidate.resolve())
                payload["status"] = "resolved" if checksum else "checksum_missing"
                payload["reason"] = None if checksum else f"Artifact {candidate.name} is configured locally, but its checksum is unresolved."
                return payload
        else:
            payload["source_url"] = urljoin(artifact_root.rstrip("/") + "/", row["file_name"])
            payload["status"] = "resolved" if checksum else "checksum_missing"
            payload["reason"] = None if checksum else f"Artifact {row['file_name']} is configured remotely, but its checksum is unresolved."
            return payload

    artifact_base_url = env.get("READINESS_CANN_ARTIFACT_BASE_URL")
    if artifact_base_url:
        payload["source_url"] = urljoin(artifact_base_url.rstrip("/") + "/", row["file_name"])
        payload["status"] = "resolved" if checksum else "checksum_missing"
        payload["reason"] = None if checksum else f"Artifact {row['file_name']} is configured remotely, but its checksum is unresolved."
        return payload

    payload["reason"] = (
        f"Managed CANN artifact {row['file_name']} is not available. Configure READINESS_CANN_ARTIFACT_ROOT, "
        f"READINESS_CANN_ARTIFACT_BASE_URL, or place the package under {local_cache_path.parent}."
    )
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_artifact(destination: Path, artifact: dict) -> Tuple[bool, str]:
    source_path = artifact.get("source_path")
    source_url = artifact.get("source_url")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source_path:
        try:
            shutil.copyfile(str(source_path), str(destination))
        except OSError as exc:
            return False, str(exc)
        return True, f"copied {Path(source_path).name}"
    if source_url:
        try:
            with urlopen(str(source_url), timeout=60) as response, destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except Exception as exc:
            return False, str(exc)
        return True, f"downloaded {artifact.get('file_name')}"
    return False, "managed CANN artifact source is unresolved"


def _resolve_installed_set_env(install_root: Path, expected_relpath: Optional[str]) -> Optional[Path]:
    if expected_relpath:
        expected = (install_root / expected_relpath).resolve()
        if expected.exists():
            return expected
    candidates = sorted(
        [
            path.resolve()
            for path in install_root.rglob("set_env.sh")
            if "ascend" in str(path).lower() or "cann" in str(path).lower()
        ]
    )
    return candidates[0] if candidates else None


def install_workspace_cann(working_dir: Path, action: dict) -> Tuple[bool, str, dict]:
    artifact = action.get("artifact") or {}
    cann_version = str(action.get("cann_version") or "").strip()
    install_root = managed_cann_root(working_dir) / cann_version
    download_path = (working_dir / ".readiness" / "downloads" / str(artifact.get("file_name") or "managed-cann.zip")).resolve()
    payload = {
        "install_root": str(install_root),
        "set_env_path": None,
        "download_path": str(download_path),
    }

    if artifact.get("status") != "resolved":
        return False, artifact.get("reason") or "managed CANN artifact is unresolved", payload

    ok, message = _fetch_artifact(download_path, artifact)
    if not ok:
        return False, message, payload

    expected_checksum = str(artifact.get("checksum") or "").strip().lower()
    actual_checksum = _sha256(download_path)
    if expected_checksum != actual_checksum.lower():
        return False, f"managed CANN checksum mismatch for {download_path.name}", payload

    if install_root.exists():
        shutil.rmtree(str(install_root))
    install_root.mkdir(parents=True, exist_ok=True)
    try:
        shutil.unpack_archive(str(download_path), str(install_root))
    except (shutil.ReadError, ValueError, OSError) as exc:
        return False, f"failed to unpack managed CANN artifact: {exc}", payload

    set_env_path = _resolve_installed_set_env(install_root, artifact.get("set_env_relpath"))
    if not set_env_path:
        return False, "managed CANN install did not produce a usable set_env.sh", payload

    payload["set_env_path"] = str(set_env_path)
    return True, f"{message} and installed workspace-local CANN {cann_version}", payload
