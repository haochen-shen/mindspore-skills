#!/usr/bin/env python3
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from asset_schema import (
    dedupe_asset_candidates,
    make_asset_candidate,
    make_asset_requirement,
    rank_asset_candidates,
)
from environment_selection import resolve_optional_path


CONFIG_SUFFIXES = {".yaml", ".yml", ".json"}
ENTRY_PATTERNS = (
    "train.py",
    "training.py",
    "finetune.py",
    "main.py",
    "infer.py",
    "inference.py",
    "predict.py",
    "run.py",
)
PATH_VALUE_KEYS = {
    "config": ("config", "config_file", "config_path"),
    "model": ("model_name_or_path", "model_path", "pretrained_model_name_or_path", "model_dir"),
    "dataset": ("dataset_dir", "dataset_path", "data_dir", "data_path", "train_file", "validation_file", "dataset"),
    "checkpoint": ("checkpoint_path", "resume_from_checkpoint", "load_checkpoint", "ckpt_path"),
}
HF_DATASET_CALL_PATTERN = re.compile(r"""load_dataset\(\s*["']([^"']+)["']""")
HF_MODEL_CALL_PATTERN = re.compile(r"""from_pretrained\(\s*["']([^"']+)["']""")
HF_SNAPSHOT_CALL_PATTERN = re.compile(r"""snapshot_download\([^)]*repo_id\s*=\s*["']([^"']+)["']""")
TRAINING_ARGUMENTS_PATTERN = re.compile(r"""\bTrainingArguments\s*\(""")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_config_values(text: str, keys: Tuple[str, ...]) -> List[str]:
    values: List[str] = []
    if not text:
        return values
    for key in keys:
        pattern = re.compile(rf"(?im)[\"']?{re.escape(key)}[\"']?\s*[:=]\s*[\"']?([^\"'\n]+)")
        for match in pattern.finditer(text):
            value = match.group(1).strip().strip(",")
            if value:
                values.append(value)
    return values


def looks_like_local_path(value: str) -> bool:
    if not value:
        return False
    return (
        value.startswith(".")
        or value.startswith("/")
        or value.startswith("\\")
        or value.startswith("~")
        or "\\" in value
        or value.endswith((".py", ".sh", ".yaml", ".yml", ".json", ".ckpt", ".pt", ".bin", ".txt"))
    )


def looks_like_hf_repo_id(value: str) -> bool:
    token = str(value or "").strip()
    if not token or looks_like_local_path(token):
        return False
    if token.count("/") != 1:
        return False
    owner, repo = token.split("/", 1)
    if not owner or not repo:
        return False
    if any(part.strip() != part or " " in part for part in (owner, repo)):
        return False
    return True


def resolve_entry_scripts(root: Path, files: List[Path], entry_candidates: List[Dict[str, object]]) -> List[Path]:
    results: List[Path] = []
    seen = set()
    for item in entry_candidates:
        path = resolve_optional_path(str(item.get("value") or ""), root)
        if not path or not path.exists():
            continue
        normalized = str(path.resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        results.append(path)
    if results:
        return results
    for name in ENTRY_PATTERNS:
        path = root / name
        if path.exists():
            results.append(path)
    return results


def resolve_hf_cache_layout(root: Path) -> Dict[str, object]:
    explicit_hub = os.environ.get("HUGGINGFACE_HUB_CACHE")
    explicit_datasets = os.environ.get("HF_DATASETS_CACHE")
    explicit_hf_home = os.environ.get("HF_HOME")

    if explicit_hub or explicit_datasets:
        hub_cache = Path(explicit_hub or (root / "huggingface-cache" / "hub")).resolve()
        datasets_cache = Path(explicit_datasets or (root / "huggingface-cache" / "datasets")).resolve()
        hf_home = Path(explicit_hf_home).resolve() if explicit_hf_home else None
        source = "explicit_cache_env"
    elif explicit_hf_home:
        hf_home = Path(explicit_hf_home).resolve()
        hub_cache = (hf_home / "hub").resolve()
        datasets_cache = (hf_home / "datasets").resolve()
        source = "explicit_hf_home"
    else:
        hf_home = (root / "huggingface-cache").resolve()
        hub_cache = (hf_home / "hub").resolve()
        datasets_cache = (hf_home / "datasets").resolve()
        source = "working_dir_default"

    return {
        "source": source,
        "hf_home": str(hf_home) if hf_home else None,
        "hub_cache": str(hub_cache),
        "datasets_cache": str(datasets_cache),
    }


def _repo_tokens(repo_id: str, kind: str) -> List[str]:
    owner, repo = repo_id.split("/", 1)
    tokens = [
        f"{owner}___{repo}",
        f"{owner}--{repo}",
        repo,
    ]
    if kind == "model":
        tokens.insert(0, f"models--{owner}--{repo}")
    return tokens


def _matching_cache_dirs(base_root: Path, repo_id: str, kind: str) -> List[Path]:
    if not base_root.exists() or not base_root.is_dir():
        return []
    tokens = [token.lower() for token in _repo_tokens(repo_id, kind)]
    matches: List[Path] = []
    for child in base_root.iterdir():
        if not child.is_dir():
            continue
        lowered = child.name.lower()
        if any(token in lowered for token in tokens):
            matches.append(child.resolve())
    return matches


def _callsite_matches(pattern: re.Pattern[str], text: str, entry_script: Path) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if not match:
            continue
        results.append(
            {
                "repo_id": match.group(1).strip(),
                "entry_script": str(entry_script),
                "callsite": f"{entry_script.name}:{index}",
                "line": line.strip(),
            }
        )
    return results


def analyze_entry_scripts(entry_scripts: Iterable[Path]) -> Dict[str, object]:
    model_hints: List[Dict[str, str]] = []
    dataset_hints: List[Dict[str, str]] = []
    inline_config: List[Dict[str, str]] = []
    for entry_script in entry_scripts:
        text = read_text(entry_script)
        if not text:
            continue
        model_hints.extend(_callsite_matches(HF_MODEL_CALL_PATTERN, text, entry_script))
        model_hints.extend(_callsite_matches(HF_SNAPSHOT_CALL_PATTERN, text, entry_script))
        dataset_hints.extend(_callsite_matches(HF_DATASET_CALL_PATTERN, text, entry_script))
        if TRAINING_ARGUMENTS_PATTERN.search(text):
            inline_config.append(
                {
                    "entry_script": str(entry_script),
                    "callsite": f"{entry_script.name}:TrainingArguments",
                    "line": "TrainingArguments(...) detected",
                }
            )
    return {
        "model_hints": model_hints,
        "dataset_hints": dataset_hints,
        "inline_config": inline_config,
    }


def _local_candidate(kind: str, path: Path, label: str, source: str, confidence: float, evidence: Optional[List[str]] = None) -> Dict[str, object]:
    return make_asset_candidate(
        kind,
        "local_path",
        label=label,
        locator={"path": str(path)},
        confidence=confidence,
        selection_source=source,
        evidence=evidence,
        exists=path.exists(),
    )


def _hf_hub_candidate(kind: str, repo_id: str, label: str, source: str, confidence: float, *, split: Optional[str] = None, evidence: Optional[List[str]] = None) -> Dict[str, object]:
    locator: Dict[str, object] = {"repo_id": repo_id}
    if split:
        locator["split"] = split
    return make_asset_candidate(
        kind,
        "hf_hub",
        label=label,
        locator=locator,
        confidence=confidence,
        selection_source=source,
        evidence=evidence,
    )


def _hf_cache_candidate(kind: str, repo_id: str, cache_path: Path, label: str, source: str, confidence: float, *, split: Optional[str] = None, evidence: Optional[List[str]] = None) -> Dict[str, object]:
    locator: Dict[str, object] = {
        "repo_id": repo_id,
        "cache_path": str(cache_path),
    }
    if split:
        locator["split"] = split
    return make_asset_candidate(
        kind,
        "hf_cache",
        label=label,
        locator=locator,
        confidence=confidence,
        selection_source=source,
        evidence=evidence,
        exists=cache_path.exists(),
    )


def _script_remote_candidate(kind: str, repo_id: str, hint: Dict[str, str], confidence: float) -> Dict[str, object]:
    locator: Dict[str, object] = {
        "repo_id": repo_id,
        "entry_script": hint.get("entry_script"),
        "callsite": hint.get("callsite"),
    }
    if kind == "dataset":
        locator["split"] = "train"
    return make_asset_candidate(
        kind,
        "script_managed_remote",
        label=f"script-managed {kind} download: {repo_id}",
        locator=locator,
        confidence=confidence,
        selection_source="script_analysis",
        evidence=[str(hint.get("line") or ""), str(hint.get("callsite") or "")],
    )


def _inline_config_candidate(hint: Dict[str, str]) -> Dict[str, object]:
    return make_asset_candidate(
        "config",
        "inline_config",
        label=f"inline config in {Path(str(hint.get('entry_script') or '')).name}",
        locator={
            "entry_script": hint.get("entry_script"),
            "callsite": hint.get("callsite"),
        },
        confidence=0.88,
        selection_source="script_analysis",
        evidence=[str(hint.get("line") or ""), str(hint.get("callsite") or "")],
    )


def _build_config_assets(root: Path, args: object, config_candidates: List[Dict[str, object]], script_hints: Dict[str, object]) -> Dict[str, object]:
    candidates: List[Dict[str, object]] = []
    explicit_candidate_id = None

    explicit_config = resolve_optional_path(getattr(args, "config_path", None), root)
    if explicit_config:
        explicit_candidate = _local_candidate("config", explicit_config, f"explicit config {explicit_config.name}", "explicit_input", 0.99)
        explicit_candidate_id = explicit_candidate["id"]
        candidates.append(explicit_candidate)

    for item in config_candidates:
        path = resolve_optional_path(str(item.get("value") or ""), root)
        if not path:
            continue
        candidates.append(
            _local_candidate(
                "config",
                path,
                str(item.get("label") or f"config file {path.name}"),
                str(item.get("selection_source") or "workspace_scan"),
                float(item.get("confidence") or 0.74),
                evidence=[str(item.get("value") or "")],
            )
        )

    for hint in script_hints.get("inline_config") or []:
        candidates.append(_inline_config_candidate(hint))

    return {
        "requirement": make_asset_requirement("config", required=False, reason="config file is optional unless the launcher requires one"),
        "candidates": rank_asset_candidates(candidates),
        "explicit_candidate_id": explicit_candidate_id,
    }


def _add_config_hint_candidates(kind: str, root: Path, config_candidates: List[Dict[str, object]], repo_split: Optional[str] = None) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for config_candidate in config_candidates:
        config_path = resolve_optional_path(str(config_candidate.get("value") or ""), root)
        if not config_path or not config_path.exists():
            continue
        text = read_text(config_path)
        for raw_value in parse_config_values(text, PATH_VALUE_KEYS[kind]):
            local = resolve_optional_path(raw_value, root) if looks_like_local_path(raw_value) else None
            evidence = [f"{config_path.name}: {raw_value}"]
            if local:
                results.append(_local_candidate(kind, local, f"{kind} path from {config_path.name}", "config_scan", 0.75, evidence))
            elif looks_like_hf_repo_id(raw_value):
                results.append(_hf_hub_candidate(kind, raw_value, f"HF Hub {kind} from {config_path.name}", "config_scan", 0.72, split=repo_split, evidence=evidence))
    return results


def _discover_cache_candidates(kind: str, repo_id: str, cache_layout: Dict[str, object], *, split: Optional[str] = None) -> List[Dict[str, object]]:
    if kind == "dataset":
        cache_root = Path(str(cache_layout.get("datasets_cache") or ""))
    else:
        cache_root = Path(str(cache_layout.get("hub_cache") or ""))
    matches = _matching_cache_dirs(cache_root, repo_id, kind)
    return [
        _hf_cache_candidate(
            kind,
            repo_id,
            match,
            f"HF cache {kind}: {repo_id}",
            "hf_cache_scan",
            0.83,
            split=split,
            evidence=[str(match)],
        )
        for match in matches
    ]


def _build_model_assets(root: Path, args: object, config_candidates: List[Dict[str, object]], script_hints: Dict[str, object], cache_layout: Dict[str, object], target_hint: Optional[str]) -> Dict[str, object]:
    candidates: List[Dict[str, object]] = []
    explicit_candidate_id = None

    explicit_model = resolve_optional_path(getattr(args, "model_path", None), root)
    if explicit_model:
        explicit_candidate = _local_candidate("model", explicit_model, f"explicit model {explicit_model.name}", "explicit_input", 0.99)
        explicit_candidate_id = explicit_candidate["id"]
        candidates.append(explicit_candidate)

    explicit_model_hub = getattr(args, "model_hub_id", None)
    if explicit_model_hub:
        explicit_hub_candidate = _hf_hub_candidate("model", str(explicit_model_hub), f"explicit model repo {explicit_model_hub}", "explicit_input", 0.99)
        explicit_candidate_id = explicit_hub_candidate["id"]
        candidates.append(explicit_hub_candidate)

    for name in ("model", "models"):
        path = root / name
        if path.exists():
            candidates.append(_local_candidate("model", path, f"workspace model path {name}", "workspace_scan", 0.82))

    candidates.extend(_add_config_hint_candidates("model", root, config_candidates))

    for hint in script_hints.get("model_hints") or []:
        repo_id = str(hint.get("repo_id") or "")
        if not looks_like_hf_repo_id(repo_id):
            continue
        candidates.append(_script_remote_candidate("model", repo_id, hint, 0.84))
        candidates.append(_hf_hub_candidate("model", repo_id, f"HF Hub model {repo_id}", "script_analysis", 0.79, evidence=[str(hint.get("callsite") or "")]))
        candidates.extend(_discover_cache_candidates("model", repo_id, cache_layout))

    required = target_hint in {"training", "inference"} or bool(candidates)
    return {
        "requirement": make_asset_requirement("model", required=required, reason="model weights or identifiers are needed before launch"),
        "candidates": rank_asset_candidates(candidates),
        "explicit_candidate_id": explicit_candidate_id,
    }


def _build_dataset_assets(root: Path, args: object, config_candidates: List[Dict[str, object]], script_hints: Dict[str, object], cache_layout: Dict[str, object], target_hint: Optional[str]) -> Dict[str, object]:
    candidates: List[Dict[str, object]] = []
    explicit_candidate_id = None
    dataset_split = getattr(args, "dataset_split", None) or "train"

    explicit_dataset = resolve_optional_path(getattr(args, "dataset_path", None), root)
    if explicit_dataset:
        explicit_candidate = _local_candidate("dataset", explicit_dataset, f"explicit dataset {explicit_dataset.name}", "explicit_input", 0.99)
        explicit_candidate_id = explicit_candidate["id"]
        candidates.append(explicit_candidate)

    explicit_dataset_hub = getattr(args, "dataset_hub_id", None)
    if explicit_dataset_hub:
        explicit_hub_candidate = _hf_hub_candidate(
            "dataset",
            str(explicit_dataset_hub),
            f"explicit dataset repo {explicit_dataset_hub}",
            "explicit_input",
            0.99,
            split=dataset_split,
        )
        explicit_candidate_id = explicit_hub_candidate["id"]
        candidates.append(explicit_hub_candidate)

    for name in ("dataset", "data"):
        path = root / name
        if path.exists():
            candidates.append(_local_candidate("dataset", path, f"workspace dataset path {name}", "workspace_scan", 0.82))

    candidates.extend(_add_config_hint_candidates("dataset", root, config_candidates, repo_split=dataset_split))

    for hint in script_hints.get("dataset_hints") or []:
        repo_id = str(hint.get("repo_id") or "")
        if not looks_like_hf_repo_id(repo_id):
            continue
        candidates.append(_script_remote_candidate("dataset", repo_id, hint, 0.86))
        candidates.append(_hf_hub_candidate("dataset", repo_id, f"HF Hub dataset {repo_id}", "script_analysis", 0.8, split=dataset_split, evidence=[str(hint.get("callsite") or "")]))
        candidates.extend(_discover_cache_candidates("dataset", repo_id, cache_layout, split=dataset_split))

    required = target_hint == "training" or bool(candidates)
    return {
        "requirement": make_asset_requirement("dataset", required=required, reason="training workloads need a dataset source before launch"),
        "candidates": rank_asset_candidates(candidates),
        "explicit_candidate_id": explicit_candidate_id,
    }


def _build_checkpoint_assets(root: Path, args: object, config_candidates: List[Dict[str, object]], files: List[Path]) -> Dict[str, object]:
    candidates: List[Dict[str, object]] = []
    explicit_candidate_id = None

    explicit_checkpoint = resolve_optional_path(getattr(args, "checkpoint_path", None), root)
    if explicit_checkpoint:
        explicit_candidate = _local_candidate("checkpoint", explicit_checkpoint, f"explicit checkpoint {explicit_checkpoint.name}", "explicit_input", 0.99)
        explicit_candidate_id = explicit_candidate["id"]
        candidates.append(explicit_candidate)

    candidates.extend(_add_config_hint_candidates("checkpoint", root, config_candidates))

    checkpoints_root = root / "checkpoints"
    if checkpoints_root.exists():
        candidates.append(_local_candidate("checkpoint", checkpoints_root, "workspace checkpoints directory", "workspace_scan", 0.78))

    for path in files:
        if path.suffix.lower() in {".ckpt", ".pt", ".bin"}:
            candidates.append(_local_candidate("checkpoint", path, f"workspace checkpoint file {path.name}", "workspace_scan", 0.7))

    return {
        "requirement": make_asset_requirement("checkpoint", required=False, reason="checkpoint is optional unless resuming from one"),
        "candidates": rank_asset_candidates(candidates),
        "explicit_candidate_id": explicit_candidate_id,
    }


def discover_asset_catalog(
    *,
    root: Path,
    files: List[Path],
    entry_candidates: List[Dict[str, object]],
    config_candidates: List[Dict[str, object]],
    args: object,
    target_hint: Optional[str],
) -> Dict[str, object]:
    entry_scripts = resolve_entry_scripts(root, files, entry_candidates)
    script_hints = analyze_entry_scripts(entry_scripts)
    cache_layout = resolve_hf_cache_layout(root)

    assets = {
        "config": _build_config_assets(root, args, config_candidates, script_hints),
        "model": _build_model_assets(root, args, config_candidates, script_hints, cache_layout, target_hint),
        "dataset": _build_dataset_assets(root, args, config_candidates, script_hints, cache_layout, target_hint),
        "checkpoint": _build_checkpoint_assets(root, args, config_candidates, files),
    }

    return {
        "assets": assets,
        "script_hints": script_hints,
        "cache_layout": cache_layout,
        "entry_scripts": [str(path) for path in entry_scripts],
    }
