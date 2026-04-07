#!/usr/bin/env python3
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

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
    {
        "arch": "x86_64",
        "cann": "8.5.0",
        "toolkit_file_name": "Ascend-cann-toolkit_8.5.0_linux-x86_64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.5.0_linux-x86_64.run",
    },
    {
        "arch": "aarch64",
        "cann": "8.5.0",
        "toolkit_file_name": "Ascend-cann-toolkit_8.5.0_linux-aarch64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.5.0_linux-aarch64.run",
    },
    {
        "arch": "x86_64",
        "cann": "8.3.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.3.RC1_linux-x86_64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.3.RC1_linux-x86_64.run",
    },
    {
        "arch": "aarch64",
        "cann": "8.3.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.3.RC1_linux-aarch64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.3.RC1_linux-aarch64.run",
    },
    {
        "arch": "x86_64",
        "cann": "8.2.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.2.RC1_linux-x86_64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.2.RC1_linux-x86_64.run",
    },
    {
        "arch": "aarch64",
        "cann": "8.2.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.2.RC1_linux-aarch64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.2.RC1_linux-aarch64.run",
    },
    {
        "arch": "x86_64",
        "cann": "8.1.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.1.RC1_linux-x86_64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.1.RC1_linux-x86_64.run",
    },
    {
        "arch": "aarch64",
        "cann": "8.1.RC1",
        "toolkit_file_name": "Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run",
        "ops_file_pattern": "Ascend-cann-{chip_type}-ops_8.1.RC1_linux-aarch64.run",
    },
]
VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)+(?:\.RC\d+)?)", re.IGNORECASE)
ETAG_MD5_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
DRIVER_PATTERNS = (
    re.compile(r"driver(?:\s+version)?\s*[:=]\s*([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
    re.compile(r"driver\s+([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
)
FIRMWARE_PATTERNS = (
    re.compile(r"firmware(?:\s+version)?\s*[:=]\s*([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
    re.compile(r"firmware\s+([0-9][0-9A-Za-z.\-_]+)", re.IGNORECASE),
)
CHIP_TYPE_PATTERNS = (
    (re.compile(r"\b910b\b", re.IGNORECASE), "910b"),
    (re.compile(r"\b910\b", re.IGNORECASE), "910"),
    (re.compile(r"\b310p\b", re.IGNORECASE), "310p"),
    (re.compile(r"\b310b\b", re.IGNORECASE), "310b"),
    (re.compile(r"\ba3\b", re.IGNORECASE), "A3"),
    (re.compile(r"\b950\b", re.IGNORECASE), "A3"),
    (re.compile(r"\ba2\b", re.IGNORECASE), "910b"),
)
CHIP_TYPE_ALIASES = {
    "910": "910",
    "910b": "910b",
    "310p": "310p",
    "310b": "310b",
    "a2": "910b",
    "a3": "A3",
    "950": "A3",
}
MANAGED_CANN_SET_ENV_RELPATH = "cann/set_env.sh"
HIASCEND_DOWNLOAD_PAGE = "https://www.hiascend.com/cann/download"
HIASCEND_SERVICE_BASE = "https://www.hiascend.com/ascendgateway/ascendservice"
HIASCEND_CANN_INFO_CATEGORY = 0
HIASCEND_CANN_INFO_LANG = "zh"
OFFICIAL_PACKAGE_TYPE_RANK = {"run": 0}
OPS_PACKAGE_TYPE = "toolkit"


def normalize_arch(value: Optional[str]) -> Optional[str]:
    token = (value or "").strip().lower()
    if token in {"x86_64", "amd64"}:
        return "x86_64"
    if token in {"aarch64", "arm64"}:
        return "aarch64"
    return token or None


def normalize_chip_type(value: Optional[str]) -> Optional[str]:
    token = (value or "").strip().lower()
    return CHIP_TYPE_ALIASES.get(token) or None


def managed_cann_root(working_dir: Path) -> Path:
    return (working_dir / "cann").resolve()


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


def _detect_chip_type_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for pattern, chip_type in CHIP_TYPE_PATTERNS:
        if pattern.search(text):
            return chip_type
    return None


def detect_host_facts(environ: Optional[Dict[str, str]] = None) -> dict:
    env = environ or os.environ
    platform_name = (env.get("READINESS_HOST_PLATFORM") or platform.system()).strip().lower()
    arch = normalize_arch(env.get("READINESS_HOST_ARCH") or platform.machine())
    driver_version = env.get("READINESS_DRIVER_VERSION")
    firmware_version = env.get("READINESS_FIRMWARE_VERSION")
    chip_type = normalize_chip_type(env.get("READINESS_CHIP_TYPE"))
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
    if chip_type:
        probe_source.append("env:READINESS_CHIP_TYPE")

    npu_smi_output = None
    if not driver_version or not firmware_version or not chip_type:
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
            if not chip_type:
                chip_type = _detect_chip_type_from_text(npu_smi_output)
                if chip_type:
                    probe_source.append("npu-smi:chip_type")

    supported_managed_cann = platform_name == "linux" and arch in SUPPORTED_MANAGED_CANN_ARCHES
    return {
        "host_platform": platform_name,
        "host_arch": arch,
        "driver_version": driver_version,
        "firmware_version": firmware_version,
        "chip_type": chip_type,
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


def artifact_env_token(arch: str, cann_version: str, chip_type: Optional[str] = None) -> str:
    normalized_version = normalize_cann_version(cann_version) or cann_version
    parts = [str(arch), str(normalized_version)]
    if chip_type:
        parts.append(str(chip_type))
    return "_".join(parts).upper().replace(".", "_").replace("-", "_")


def _package_token(package_kind: str, arch: str, cann_version: str, chip_type: Optional[str] = None) -> str:
    suffix = artifact_env_token(arch, cann_version, chip_type if package_kind == "ops" else None)
    return f"{package_kind.upper()}_{suffix}"


def _artifact_row(arch: Optional[str], cann_version: Optional[str]) -> Optional[dict]:
    return next((item for item in ARTIFACT_ROWS if item["arch"] == arch and item["cann"] == cann_version), None)


def _artifact_spec(package_kind: str, row: dict, chip_type: Optional[str]) -> dict:
    if package_kind == "toolkit":
        file_name = row["toolkit_file_name"]
    else:
        file_name = str(row["ops_file_pattern"]).format(chip_type=chip_type)
    return {
        "package_kind": package_kind,
        "file_name": file_name,
        "set_env_relpath": MANAGED_CANN_SET_ENV_RELPATH if package_kind == "toolkit" else None,
    }


def _normalized_remote_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    encoded_path = quote(parsed.path, safe="/:@%+-._~")
    encoded_query = quote(parsed.query, safe="=&%+-._~")
    return urlunsplit((parsed.scheme, parsed.netloc, encoded_path, encoded_query, parsed.fragment))


def _build_request(url: str, method: str = "GET", accept: str = "*/*") -> Request:
    return Request(
        _normalized_remote_url(url),
        method=method,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": accept,
            "Referer": HIASCEND_DOWNLOAD_PAGE,
        },
    )


def _request_json(url: str, timeout_seconds: int = 30) -> Optional[dict]:
    try:
        with urlopen(_build_request(url, method="GET", accept="application/json, text/plain, */*"), timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))
    except Exception:
        return None


def _remote_checksum_from_headers(source_url: str, timeout_seconds: int = 30) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        with urlopen(_build_request(source_url, method="HEAD"), timeout=timeout_seconds) as response:
            etag = str(response.headers.get("ETag") or "").strip().strip('"').lower()
    except Exception:
        return None, None, None
    if ETAG_MD5_PATTERN.fullmatch(etag):
        return "md5", etag, "remote:etag"
    return None, None, None


def _official_package_rank(item: dict, package_kind: str, chip_type: Optional[str]) -> Tuple[int, int, str]:
    package_type = str(item.get("packageType") or "").strip().lower()
    software_name = str(item.get("softwareName") or "")
    if package_kind == "toolkit":
        kind_rank = 0 if "toolkit" in software_name.lower() else 1
    else:
        chip_token = str(chip_type or "").lower()
        kind_rank = 0 if f"-{chip_token}-ops_" in software_name.lower() else 1
    return (
        OFFICIAL_PACKAGE_TYPE_RANK.get(package_type, 99),
        kind_rank,
        software_name.lower(),
    )


def _resolve_official_cann_artifact(
    package_kind: str,
    arch: Optional[str],
    cann_version: Optional[str],
    chip_type: Optional[str] = None,
) -> Optional[dict]:
    if not arch or not cann_version:
        return None
    url = f"{HIASCEND_SERVICE_BASE}/cann/info/{HIASCEND_CANN_INFO_LANG}/{HIASCEND_CANN_INFO_CATEGORY}?versionName={cann_version}"
    response = _request_json(url)
    data = (response or {}).get("data") or {}
    package_list = data.get("packageList") or []
    candidates = []
    for item in package_list:
        package_type = str(item.get("packageType") or "").strip().lower()
        cpu_name = normalize_arch(item.get("cpuName"))
        software_name = str(item.get("softwareName") or "")
        lowered_name = software_name.lower()
        if cpu_name != arch:
            continue
        if package_type not in OFFICIAL_PACKAGE_TYPE_RANK:
            continue
        if package_kind == "toolkit":
            if "toolkit" not in lowered_name:
                continue
        else:
            if not chip_type or f"-{str(chip_type).lower()}-ops_" not in lowered_name:
                continue
        candidates.append(item)
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda item: _official_package_rank(item, package_kind, chip_type))
    selected = candidates[0]
    signature_urls = [item.strip() for item in str(selected.get("digitalSignatureUrl") or "").split(",") if item.strip()]
    checksum_kind, checksum_value, checksum_source = _remote_checksum_from_headers(str(selected.get("downloadUrl") or ""))
    return {
        "package_kind": package_kind,
        "file_name": str(selected.get("softwareName") or ""),
        "source_url": _normalized_remote_url(str(selected.get("downloadUrl") or "")),
        "signature_urls": signature_urls,
        "checksum_kind": checksum_kind,
        "checksum": checksum_value,
        "checksum_source": checksum_source,
        "set_env_relpath": MANAGED_CANN_SET_ENV_RELPATH if package_kind == "toolkit" else None,
    }


def resolve_cann_package_artifact(
    working_dir: Path,
    package_kind: str,
    arch: Optional[str],
    cann_version: Optional[str],
    chip_type: Optional[str] = None,
    environ: Optional[Dict[str, str]] = None,
) -> dict:
    env = environ or os.environ
    payload = {
        "status": "unresolved",
        "reason": None,
        "package_kind": package_kind,
        "file_name": None,
        "set_env_relpath": MANAGED_CANN_SET_ENV_RELPATH if package_kind == "toolkit" else None,
        "source_path": None,
        "source_url": None,
        "checksum": None,
        "checksum_kind": "sha256",
        "checksum_source": None,
        "signature_urls": [],
    }
    if not arch or not cann_version:
        payload["reason"] = f"Managed CANN {package_kind} artifact lookup requires both arch and cann_version."
        return payload
    if package_kind == "ops" and not chip_type:
        payload["reason"] = "Managed CANN ops artifact lookup requires chip_type."
        return payload

    row = _artifact_row(arch, cann_version)
    if not row:
        payload["reason"] = f"No managed CANN artifact mapping is available for arch={arch}, cann_version={cann_version}."
        return payload
    spec = _artifact_spec(package_kind, row, chip_type)
    payload["file_name"] = spec["file_name"]
    payload["set_env_relpath"] = spec.get("set_env_relpath")

    token = _package_token(package_kind, arch, cann_version, chip_type)
    legacy_token = artifact_env_token(arch, cann_version)
    explicit_sha_env = f"READINESS_CANN_{package_kind.upper()}_SHA256_{token}"
    checksum = env.get(explicit_sha_env)
    if package_kind == "toolkit" and not checksum:
        checksum = env.get(f"READINESS_CANN_SHA256_{legacy_token}")
    if checksum:
        payload["checksum"] = checksum
        payload["checksum_kind"] = "sha256"
        payload["checksum_source"] = explicit_sha_env if env.get(explicit_sha_env) else f"READINESS_CANN_SHA256_{legacy_token}"

    explicit_url_env = f"READINESS_CANN_{package_kind.upper()}_ARTIFACT_URL_{token}"
    direct_url = env.get(explicit_url_env)
    if package_kind == "toolkit" and not direct_url:
        direct_url = env.get(f"READINESS_CANN_ARTIFACT_URL_{legacy_token}")
    if direct_url:
        payload["source_url"] = _normalized_remote_url(direct_url)
        if not payload["checksum"]:
            checksum_kind, checksum_value, checksum_source = _remote_checksum_from_headers(payload["source_url"])
            if checksum_value:
                payload["checksum_kind"] = checksum_kind or "sha256"
                payload["checksum"] = checksum_value
                payload["checksum_source"] = checksum_source
        payload["status"] = "resolved" if payload["checksum"] else "checksum_missing"
        payload["reason"] = None if payload["checksum"] else f"Artifact {payload['file_name']} is configured, but its checksum is unresolved."
        return payload

    local_cache_path = (working_dir / ".readiness" / "artifacts" / "cann" / payload["file_name"]).resolve()
    if local_cache_path.exists():
        payload["source_path"] = str(local_cache_path)
        payload["status"] = "resolved" if checksum else "checksum_missing"
        payload["reason"] = None if checksum else f"Artifact {payload['file_name']} is available locally, but its checksum is unresolved."
        return payload

    artifact_root = env.get("READINESS_CANN_ARTIFACT_ROOT")
    if artifact_root:
        root_path = Path(artifact_root).expanduser()
        if root_path.exists():
            candidate = root_path / payload["file_name"] if root_path.is_dir() else root_path
            if candidate.exists():
                payload["source_path"] = str(candidate.resolve())
                payload["status"] = "resolved" if checksum else "checksum_missing"
                payload["reason"] = None if checksum else f"Artifact {candidate.name} is configured locally, but its checksum is unresolved."
                return payload
        else:
            payload["source_url"] = _normalized_remote_url(urljoin(artifact_root.rstrip("/") + "/", payload["file_name"]))
            if not payload["checksum"]:
                checksum_kind, checksum_value, checksum_source = _remote_checksum_from_headers(payload["source_url"])
                if checksum_value:
                    payload["checksum_kind"] = checksum_kind or "sha256"
                    payload["checksum"] = checksum_value
                    payload["checksum_source"] = checksum_source
            payload["status"] = "resolved" if payload["checksum"] else "checksum_missing"
            payload["reason"] = None if payload["checksum"] else f"Artifact {payload['file_name']} is configured remotely, but its checksum is unresolved."
            return payload

    artifact_base_url = env.get("READINESS_CANN_ARTIFACT_BASE_URL")
    if artifact_base_url:
        payload["source_url"] = _normalized_remote_url(urljoin(artifact_base_url.rstrip("/") + "/", payload["file_name"]))
        if not payload["checksum"]:
            checksum_kind, checksum_value, checksum_source = _remote_checksum_from_headers(payload["source_url"])
            if checksum_value:
                payload["checksum_kind"] = checksum_kind or "sha256"
                payload["checksum"] = checksum_value
                payload["checksum_source"] = checksum_source
        payload["status"] = "resolved" if payload["checksum"] else "checksum_missing"
        payload["reason"] = None if payload["checksum"] else f"Artifact {payload['file_name']} is configured remotely, but its checksum is unresolved."
        return payload

    official_artifact = _resolve_official_cann_artifact(package_kind, arch, cann_version, chip_type=chip_type)
    if official_artifact:
        payload["file_name"] = official_artifact["file_name"] or payload["file_name"]
        payload["set_env_relpath"] = official_artifact.get("set_env_relpath") or payload["set_env_relpath"]
        payload["source_url"] = official_artifact.get("source_url")
        payload["signature_urls"] = official_artifact.get("signature_urls") or []
        if not payload["checksum"] and official_artifact.get("checksum"):
            payload["checksum_kind"] = str(official_artifact.get("checksum_kind") or "sha256")
            payload["checksum"] = official_artifact.get("checksum")
            payload["checksum_source"] = official_artifact.get("checksum_source") or "official_api"
        payload["status"] = "resolved" if payload["checksum"] else "checksum_missing"
        payload["reason"] = None if payload["checksum"] else (
            f"Official CANN artifact {payload['file_name']} was resolved from {HIASCEND_DOWNLOAD_PAGE}, "
            "but its checksum is unresolved."
        )
        return payload

    payload["reason"] = (
        f"Managed CANN artifact {payload['file_name']} could not be resolved from {HIASCEND_DOWNLOAD_PAGE}. "
        f"Configure READINESS_CANN_ARTIFACT_ROOT, READINESS_CANN_ARTIFACT_BASE_URL, {explicit_url_env}, "
        f"or place the package under {local_cache_path.parent}."
    )
    return payload


def resolve_cann_artifacts(
    working_dir: Path,
    arch: Optional[str],
    cann_version: Optional[str],
    chip_type: Optional[str],
    environ: Optional[Dict[str, str]] = None,
) -> dict:
    payload = {
        "status": "unresolved",
        "reason": None,
        "cann_version": cann_version,
        "chip_type": chip_type,
        "toolkit": {},
        "ops": {},
    }
    toolkit = resolve_cann_package_artifact(working_dir, "toolkit", arch, cann_version, chip_type=None, environ=environ)
    ops = resolve_cann_package_artifact(working_dir, "ops", arch, cann_version, chip_type=chip_type, environ=environ)
    payload["toolkit"] = toolkit
    payload["ops"] = ops
    if toolkit.get("status") == "resolved" and ops.get("status") == "resolved":
        payload["status"] = "resolved"
        return payload

    statuses = [str(toolkit.get("status") or ""), str(ops.get("status") or "")]
    if "checksum_missing" in statuses:
        payload["status"] = "checksum_missing"
    else:
        payload["status"] = "artifact_unavailable"
    reasons = [reason for reason in (toolkit.get("reason"), ops.get("reason")) if reason]
    payload["reason"] = "; ".join(reasons) if reasons else "Managed CANN toolkit and ops artifacts are unresolved."
    return payload


def resolve_cann_artifact(working_dir: Path, arch: Optional[str], cann_version: Optional[str], environ: Optional[Dict[str, str]] = None) -> dict:
    return resolve_cann_package_artifact(working_dir, "toolkit", arch, cann_version, environ=environ)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5()
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
            with urlopen(_build_request(str(source_url)), timeout=60) as response, destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except Exception as exc:
            return False, str(exc)
        return True, f"downloaded {artifact.get('file_name')}"
    return False, "managed CANN artifact source is unresolved"


def _verify_artifact_checksum(download_path: Path, artifact: dict) -> Tuple[bool, str]:
    expected_checksum = str(artifact.get("checksum") or "").strip().lower()
    checksum_kind = str(artifact.get("checksum_kind") or "sha256").strip().lower()
    if checksum_kind == "md5":
        actual_checksum = _md5(download_path)
    else:
        actual_checksum = _sha256(download_path)
    if expected_checksum != actual_checksum.lower():
        return False, f"managed CANN checksum mismatch for {download_path.name}"
    return True, ""


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


def _bash_path(path: Path) -> str:
    resolved = path.resolve()
    posix = resolved.as_posix()
    drive_match = re.match(r"^([A-Za-z]):/(.*)$", posix)
    if drive_match:
        return f"/mnt/{drive_match.group(1).lower()}/{drive_match.group(2)}"
    return posix


def _run_cann_installer(package_path: Path, install_root: Path, *, package_type: Optional[str] = None) -> Tuple[bool, str]:
    command = ["bash", _bash_path(package_path), "--install", f"--install-path={_bash_path(install_root)}"]
    if package_type:
        command.append(f"--type={package_type}")
    try:
        subprocess.run(command, check=True, text=True, capture_output=True, timeout=900)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        return False, stderr or stdout or "managed CANN installer failed"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return True, ""


def install_workspace_cann(working_dir: Path, action: dict) -> Tuple[bool, str, dict]:
    artifacts = action.get("artifacts") or {}
    toolkit = artifacts.get("toolkit") or {}
    ops = artifacts.get("ops") or {}
    cann_version = str(action.get("cann_version") or "").strip()
    chip_type = str(action.get("chip_type") or artifacts.get("chip_type") or "").strip()
    install_root = managed_cann_root(working_dir) / cann_version
    toolkit_download_path = (working_dir / ".readiness" / "downloads" / str(toolkit.get("file_name") or "managed-cann-toolkit.run")).resolve()
    ops_download_path = (working_dir / ".readiness" / "downloads" / str(ops.get("file_name") or "managed-cann-ops.run")).resolve()
    payload = {
        "install_root": str(install_root),
        "set_env_path": None,
        "download_paths": {
            "toolkit": str(toolkit_download_path),
            "ops": str(ops_download_path),
        },
        "chip_type": chip_type or None,
    }

    if artifacts.get("status") != "resolved":
        return False, artifacts.get("reason") or "managed CANN artifacts are unresolved", payload

    ok, message = _fetch_artifact(toolkit_download_path, toolkit)
    if not ok:
        return False, message, payload
    ok, message_detail = _verify_artifact_checksum(toolkit_download_path, toolkit)
    if not ok:
        return False, message_detail, payload

    if install_root.exists():
        shutil.rmtree(str(install_root))
    install_root.mkdir(parents=True, exist_ok=True)

    ok, installer_error = _run_cann_installer(toolkit_download_path, install_root)
    if not ok:
        return False, installer_error, payload

    ok, ops_message = _fetch_artifact(ops_download_path, ops)
    if not ok:
        return False, ops_message, payload
    ok, ops_checksum_error = _verify_artifact_checksum(ops_download_path, ops)
    if not ok:
        return False, ops_checksum_error, payload

    ok, installer_error = _run_cann_installer(ops_download_path, install_root, package_type=OPS_PACKAGE_TYPE)
    if not ok:
        return False, installer_error, payload

    set_env_path = _resolve_installed_set_env(install_root, toolkit.get("set_env_relpath"))
    if not set_env_path:
        return False, "managed CANN install did not produce a usable set_env.sh", payload

    payload["set_env_path"] = str(set_env_path)
    return True, f"{message}; {ops_message}; installed workspace-local CANN {cann_version} ({chip_type})", payload
