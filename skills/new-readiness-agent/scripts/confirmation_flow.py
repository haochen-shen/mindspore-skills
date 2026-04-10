#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from asset_schema import make_selected_asset, rank_asset_candidates
from candidate_utils import choose_top_candidate, looks_like_local_path, merge_catalog_candidates, ranked_candidates
from environment_selection import resolve_optional_path


VALIDATION_GATE_FIELDS = (
    "target",
    "launcher",
    "framework",
    "runtime_environment",
    "entry_script",
    "config_asset",
    "model_asset",
    "dataset_asset",
    "cann_path",
)

CONFIRMATION_SEQUENCE = (
    {
        "field": "target",
        "label": "Target",
        "candidate_key": "target_candidates",
        "catalog_key": "target",
        "allow_free_text": False,
        "prompt": "Confirm the intended workflow target before continuing the readiness scan.",
    },
    {
        "field": "launcher",
        "label": "Launcher",
        "candidate_key": "launcher_candidates",
        "catalog_key": "launcher",
        "allow_free_text": False,
        "prompt": "Confirm which launcher this workspace should use.",
    },
    {
        "field": "framework",
        "label": "Framework",
        "candidate_key": "framework_candidates",
        "catalog_key": "framework",
        "allow_free_text": False,
        "prompt": "Confirm the framework stack that should run on this workspace.",
    },
    {
        "field": "runtime_environment",
        "label": "Python / Environment",
        "candidate_key": "environment",
        "allow_free_text": True,
        "manual_hint": "If none of the detected environments fit, provide the intended selected_python and selected_env_root on the next run.",
        "prompt": "Confirm the runtime Python environment that should be used for readiness checks.",
    },
    {
        "field": "entry_script",
        "label": "Entry Script",
        "candidate_key": "entry_candidates",
        "allow_free_text": True,
        "manual_hint": "Provide the local training or inference script path if it is not listed.",
        "prompt": "Confirm the entry script path for the workload.",
    },
    {
        "field": "config_asset",
        "label": "Config Asset",
        "candidate_key": "asset:config",
        "allow_free_text": True,
        "manual_hint": "Use a detected asset option, or enter local:/path, inline_config, none, or unknown.",
        "prompt": "Confirm how this workspace satisfies its runtime configuration.",
    },
    {
        "field": "model_asset",
        "label": "Model Asset",
        "candidate_key": "asset:model",
        "allow_free_text": True,
        "manual_hint": "Use a detected asset option, or enter local:/path, hf_hub:repo_id, hf_cache:/path, or unknown.",
        "prompt": "Confirm how this workspace satisfies the model requirement.",
    },
    {
        "field": "dataset_asset",
        "label": "Dataset Asset",
        "candidate_key": "asset:dataset",
        "allow_free_text": True,
        "manual_hint": "Use a detected asset option, or enter local:/path, hf_hub:repo_id, hf_cache:/path, script_managed_remote:repo_id, or unknown.",
        "prompt": "Confirm how this workspace satisfies the dataset requirement.",
    },
    {
        "field": "checkpoint_asset",
        "label": "Checkpoint Asset",
        "candidate_key": "asset:checkpoint",
        "allow_free_text": True,
        "manual_hint": "Use a detected checkpoint option, or enter local:/path, none, or unknown.",
        "prompt": "Confirm whether this workspace depends on a checkpoint before launch.",
    },
    {
        "field": "cann_path",
        "label": "CANN / set_env.sh",
        "candidate_key": "cann_candidates",
        "allow_free_text": True,
        "manual_hint": "Provide a CANN root or set_env.sh path if you already know it.",
        "prompt": "Confirm the CANN or Ascend environment path for this workspace.",
    },
)


def parse_confirmation_overrides(raw_items: Optional[List[str]]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if not raw_items:
        return overrides
    for item in raw_items:
        if "=" not in str(item):
            continue
        field_name, raw_value = str(item).split("=", 1)
        field_name = field_name.strip()
        if field_name:
            overrides[field_name] = raw_value.strip()
    return overrides


def build_numbered_options(
    field_candidates: List[Dict[str, object]],
    *,
    allow_free_text: bool,
    include_unknown: bool = True,
) -> List[Dict[str, object]]:
    options: List[Dict[str, object]] = []
    for item in field_candidates:
        options.append(
            {
                "value": item.get("value"),
                "label": item.get("label"),
                "confidence": item.get("confidence"),
                "selection_source": item.get("selection_source"),
            }
        )
    if allow_free_text:
        options.append(
            {
                "value": "__manual__",
                "label": "enter a custom value manually",
                "confidence": 0.0,
                "selection_source": "manual",
            }
        )
    if include_unknown:
        options.append(
            {
                "value": "__unknown__",
                "label": "unknown / not sure",
                "confidence": 0.0,
                "selection_source": "manual",
            }
        )
    for index, option in enumerate(options, start=1):
        option["index"] = index
    return options


def load_cached_confirmation(root: Path) -> Dict[str, object]:
    confirmation_path = root / "readiness-output" / "latest" / "new-readiness-agent" / "confirmation-latest.json"
    if not confirmation_path.exists():
        return {}
    try:
        payload = json.loads(confirmation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def asset_bundle(scan: Dict[str, object], kind: str) -> Dict[str, object]:
    catalog = scan.get("asset_catalog") if isinstance(scan.get("asset_catalog"), dict) else {}
    assets = catalog.get("assets") if isinstance(catalog.get("assets"), dict) else {}
    bundle = assets.get(kind)
    if isinstance(bundle, dict):
        return bundle
    return {"requirement": {"kind": kind, "required": False, "reason": ""}, "candidates": []}


def find_asset_candidate(asset_candidates: List[Dict[str, object]], raw_value: str) -> Optional[Dict[str, object]]:
    token = str(raw_value or "").strip()
    if not token:
        return None
    for candidate_item in asset_candidates:
        if token == candidate_item.get("id"):
            return candidate_item
        locator = candidate_item.get("locator") if isinstance(candidate_item.get("locator"), dict) else {}
        if token in {
            str(locator.get("path") or ""),
            str(locator.get("cache_path") or ""),
            str(locator.get("repo_id") or ""),
        }:
            return candidate_item
    return None


def build_asset_confirmation_options(bundle: Dict[str, object], *, allow_free_text: bool) -> List[Dict[str, object]]:
    options: List[Dict[str, object]] = []
    for candidate_item in rank_asset_candidates(bundle.get("candidates") or []):
        options.append(
            {
                "value": candidate_item.get("id"),
                "label": candidate_item.get("label"),
                "confidence": candidate_item.get("confidence"),
                "selection_source": candidate_item.get("selection_source"),
                "source_type": candidate_item.get("source_type"),
                "locator": candidate_item.get("locator"),
            }
        )
    if allow_free_text:
        options.append(
            {
                "value": "__manual__",
                "label": "enter a custom value manually",
                "confidence": 0.0,
                "selection_source": "manual",
            }
        )
    options.append(
        {
            "value": "__unknown__",
            "label": "unknown / not sure",
            "confidence": 0.0,
            "selection_source": "manual",
        }
    )
    for index, option in enumerate(options, start=1):
        option["index"] = index
    return options


def infer_manual_asset(kind: str, requirement: Dict[str, object], raw_value: str) -> Dict[str, object]:
    value = str(raw_value or "").strip()
    lowered = value.lower()
    if lowered in {"none", "__none__"}:
        return make_selected_asset(kind, requirement, source_type="none", locator={}, selection_source="manual_confirmation")
    if lowered in {"inline_config", "inline"}:
        return make_selected_asset(kind, requirement, source_type="inline_config", locator={}, selection_source="manual_confirmation")
    if value.startswith("local:"):
        return make_selected_asset(kind, requirement, source_type="local_path", locator={"path": value.split(":", 1)[1].strip()}, selection_source="manual_confirmation")
    if value.startswith("hf_cache:"):
        return make_selected_asset(kind, requirement, source_type="hf_cache", locator={"cache_path": value.split(":", 1)[1].strip()}, selection_source="manual_confirmation")
    if value.startswith("hf_hub:"):
        locator: Dict[str, object] = {"repo_id": value.split(":", 1)[1].strip()}
        if kind == "dataset":
            locator["split"] = "train"
        return make_selected_asset(kind, requirement, source_type="hf_hub", locator=locator, selection_source="manual_confirmation")
    if value.startswith("script_managed_remote:"):
        locator = {"repo_id": value.split(":", 1)[1].strip()}
        if kind == "dataset":
            locator["split"] = "train"
        return make_selected_asset(kind, requirement, source_type="script_managed_remote", locator=locator, selection_source="manual_confirmation")
    if looks_like_local_path(value):
        return make_selected_asset(kind, requirement, source_type="local_path", locator={"path": value}, selection_source="manual_confirmation")
    if kind in {"model", "dataset"} and re.match(r"^[^/\s]+/[^/\s]+$", value):
        locator = {"repo_id": value}
        if kind == "dataset":
            locator["split"] = "train"
        return make_selected_asset(kind, requirement, source_type="hf_hub", locator=locator, selection_source="manual_confirmation")
    return make_selected_asset(kind, requirement, source_type="unknown", locator={"raw": value}, selection_source="manual_confirmation")


def choose_asset(
    kind: str,
    cached_confirmation: Dict[str, object],
    bundle: Dict[str, object],
    confirmation_override: Optional[str] = None,
) -> Dict[str, object]:
    field_name = f"{kind}_asset"
    requirement = bundle.get("requirement") if isinstance(bundle.get("requirement"), dict) else {"kind": kind, "required": False, "reason": ""}
    asset_candidates = list(bundle.get("candidates") or [])
    cached_fields = cached_confirmation.get("confirmed_fields") if isinstance(cached_confirmation.get("confirmed_fields"), dict) else {}
    cached_item = cached_fields.get(field_name) if isinstance(cached_fields.get(field_name), dict) else None

    if confirmation_override is not None:
        if confirmation_override == "__unknown__":
            return {
                "value": None,
                "source": "manual_confirmation",
                "confirmed": True,
                "asset": make_selected_asset(kind, requirement, source_type="unknown", locator={}, selection_source="manual_confirmation"),
            }
        candidate_item = find_asset_candidate(asset_candidates, confirmation_override)
        if candidate_item:
            return {
                "value": candidate_item.get("id"),
                "source": "manual_confirmation",
                "confirmed": True,
                "asset": make_selected_asset(kind, requirement, candidate=candidate_item),
            }
        return {
            "value": confirmation_override,
            "source": "manual_confirmation",
            "confirmed": True,
            "asset": infer_manual_asset(kind, requirement, confirmation_override),
        }

    explicit_candidate_id = bundle.get("explicit_candidate_id")
    if explicit_candidate_id:
        explicit_candidate = find_asset_candidate(asset_candidates, str(explicit_candidate_id))
        if explicit_candidate:
            return {
                "value": explicit_candidate.get("id"),
                "source": "explicit_input",
                "confirmed": True,
                "asset": make_selected_asset(kind, requirement, candidate=explicit_candidate),
            }

    if isinstance(cached_item, dict):
        cached_asset = cached_item.get("asset") if isinstance(cached_item.get("asset"), dict) else None
        cached_value = cached_item.get("value")
        cached_confirmed = bool(cached_item.get("confirmed", False))
        if cached_asset:
            candidate_item = find_asset_candidate(asset_candidates, str(cached_value or "")) if cached_value else None
            if candidate_item:
                return {
                    "value": candidate_item.get("id"),
                    "source": "cached_confirmation",
                    "confirmed": cached_confirmed,
                    "asset": make_selected_asset(kind, requirement, candidate=candidate_item),
                }
            return {
                "value": cached_value,
                "source": "cached_confirmation",
                "confirmed": cached_confirmed,
                "asset": cached_asset,
            }

    top_candidate = asset_candidates[0] if asset_candidates else None
    if top_candidate:
        return {
            "value": top_candidate.get("id"),
            "source": "auto_recommended",
            "confirmed": False,
            "asset": make_selected_asset(kind, requirement, candidate=top_candidate),
        }

    return {
        "value": None,
        "source": "missing",
        "confirmed": False,
        "asset": make_selected_asset(kind, requirement, source_type="unknown", locator={}, selection_source="missing"),
    }


def choose_value(
    field_name: str,
    explicit_value: Optional[str],
    cached_confirmation: Dict[str, object],
    field_candidates: List[Dict[str, object]],
    confirmation_override: Optional[str] = None,
) -> Dict[str, object]:
    cached_fields = cached_confirmation.get("confirmed_fields") if isinstance(cached_confirmation.get("confirmed_fields"), dict) else {}
    cached_item = cached_fields.get(field_name) if isinstance(cached_fields.get(field_name), dict) else None

    if confirmation_override is not None:
        if confirmation_override == "__unknown__":
            return {"value": None, "source": "manual_confirmation", "confirmed": True}
        return {"value": confirmation_override, "source": "manual_confirmation", "confirmed": True}
    if explicit_value not in {None, ""}:
        return {"value": explicit_value, "source": "explicit_input", "confirmed": True}
    if isinstance(cached_item, dict) and bool(cached_item.get("confirmed", False)):
        return {"value": cached_item.get("value"), "source": "cached_confirmation", "confirmed": True}
    if isinstance(cached_item, dict) and cached_item.get("value") not in {None, ""}:
        return {
            "value": cached_item.get("value"),
            "source": "cached_confirmation",
            "confirmed": bool(cached_item.get("confirmed", False)),
        }
    top = choose_top_candidate(list(field_candidates))
    if not top:
        return {"value": None, "source": "missing", "confirmed": False}
    return {"value": top.get("value"), "source": "auto_recommended", "confirmed": False}


def choose_environment(
    root: Path,
    args: object,
    cached_confirmation: Dict[str, object],
    environment_result: Dict[str, object],
    confirmation_override: Optional[str] = None,
) -> Dict[str, object]:
    candidates = environment_result.get("candidates") or []
    explicit_python = getattr(args, "selected_python", None)
    explicit_env_root = getattr(args, "selected_env_root", None)
    cached_fields = cached_confirmation.get("confirmed_fields") if isinstance(cached_confirmation.get("confirmed_fields"), dict) else {}

    def with_runtime_env_fields(
        candidate_item: Dict[str, object],
        *,
        python_value: Optional[str] = None,
        env_value: Optional[str] = None,
    ) -> Dict[str, object]:
        normalized = dict(candidate_item)
        if python_value and not normalized.get("python_path"):
            normalized["python_path"] = python_value
        if env_value and not normalized.get("env_root"):
            normalized["env_root"] = env_value
        return normalized

    if confirmation_override is not None:
        if confirmation_override == "__unknown__":
            return {"candidate": None, "source": "manual_confirmation", "confirmed": True}
        for candidate_item in candidates:
            if confirmation_override in {candidate_item.get("id"), candidate_item.get("python_path"), candidate_item.get("env_root")}:
                return {"candidate": candidate_item, "source": "manual_confirmation", "confirmed": True}

    if explicit_python or explicit_env_root:
        explicit_python_value = str(resolve_optional_path(explicit_python, root) or explicit_python) if explicit_python else None
        explicit_env_value = str(resolve_optional_path(explicit_env_root, root) or explicit_env_root) if explicit_env_root else None
        for candidate_item in candidates:
            if explicit_python_value and candidate_item.get("python_path") == explicit_python_value:
                return {
                    "candidate": with_runtime_env_fields(candidate_item, python_value=explicit_python_value, env_value=explicit_env_value),
                    "source": "explicit_input",
                    "confirmed": True,
                }
            if explicit_env_value and candidate_item.get("env_root") == explicit_env_value:
                return {
                    "candidate": with_runtime_env_fields(candidate_item, python_value=explicit_python_value, env_value=explicit_env_value),
                    "source": "explicit_input",
                    "confirmed": True,
                }

    cached_env = cached_fields.get("selected_env_root") if isinstance(cached_fields, dict) else None
    cached_python = cached_fields.get("selected_python") if isinstance(cached_fields, dict) else None
    cached_env_value = cached_env.get("value") if isinstance(cached_env, dict) else None
    cached_python_value = cached_python.get("value") if isinstance(cached_python, dict) else None
    cached_confirmed = bool(
        (isinstance(cached_env, dict) and cached_env.get("confirmed", False))
        and (isinstance(cached_python, dict) and cached_python.get("confirmed", False))
    )
    if cached_confirmed and cached_env_value in {None, ""} and cached_python_value in {None, ""}:
        return {"candidate": None, "source": "cached_confirmation", "confirmed": True}
    if cached_env_value or cached_python_value:
        for candidate_item in candidates:
            if cached_env_value and candidate_item.get("env_root") == cached_env_value:
                return {
                    "candidate": with_runtime_env_fields(candidate_item, python_value=cached_python_value, env_value=cached_env_value),
                    "source": "cached_confirmation",
                    "confirmed": cached_confirmed,
                }
            if cached_python_value and candidate_item.get("python_path") == cached_python_value:
                return {
                    "candidate": with_runtime_env_fields(candidate_item, python_value=cached_python_value, env_value=cached_env_value),
                    "source": "cached_confirmation",
                    "confirmed": cached_confirmed,
                }
        synthetic_candidate = {
            "id": "env-cached",
            "kind": "cached-confirmation",
            "selection_source": "cached_confirmation",
            "label": "cached runtime environment",
            "python_path": cached_python_value,
            "env_root": cached_env_value,
            "status": "unresolved",
            "reason": "cached runtime environment was not rediscovered in the current scan",
            "confidence": 0.51,
            "recommended": True,
        }
        candidates.insert(0, synthetic_candidate)
        return {"candidate": synthetic_candidate, "source": "cached_confirmation", "confirmed": cached_confirmed}

    recommended = choose_top_candidate(list(candidates))
    if not recommended:
        return {"candidate": None, "source": "missing", "confirmed": False}
    return {"candidate": recommended, "source": "auto_recommended", "confirmed": False}


def confirmation_definition(field_name: str) -> Dict[str, object]:
    for item in CONFIRMATION_SEQUENCE:
        if item["field"] == field_name:
            return dict(item)
    raise KeyError(field_name)


def confirmation_field_is_confirmed(field_name: str, confirmed_fields: Dict[str, object]) -> bool:
    item = confirmed_fields.get(field_name)
    return isinstance(item, dict) and bool(item.get("confirmed", False))


def build_runtime_environment_options(scan: Dict[str, object]) -> List[Dict[str, object]]:
    options: List[Dict[str, object]] = []
    for item in ranked_candidates(list(scan["environment"]["candidates"])):
        options.append(
            {
                "value": item.get("id"),
                "label": item.get("label"),
                "confidence": item.get("confidence"),
                "selection_source": item.get("selection_source"),
                "python_path": item.get("python_path"),
                "env_root": item.get("env_root"),
            }
        )
    options.append(
        {
            "value": "__manual__",
            "label": "enter a custom environment manually",
            "confidence": 0.0,
            "selection_source": "manual",
        }
    )
    options.append(
        {
            "value": "__unknown__",
            "label": "unknown / not sure",
            "confidence": 0.0,
            "selection_source": "manual",
        }
    )
    for index, option in enumerate(options, start=1):
        option["index"] = index
    return options


def active_confirmation_sequence(scan: Dict[str, object], profile: Dict[str, object]) -> List[Dict[str, object]]:
    launcher_value = str(profile.get("launcher") or "")
    assets = profile.get("assets") if isinstance(profile.get("assets"), dict) else {}
    sequence: List[Dict[str, object]] = []
    for item in CONFIRMATION_SEQUENCE:
        field_name = str(item.get("field"))
        if field_name == "config_asset":
            bundle = assets.get("config") if isinstance(assets.get("config"), dict) else {}
            bundle_candidates = list(bundle.get("candidates") or [])
            bundle_requirement = bundle.get("requirement") if isinstance(bundle.get("requirement"), dict) else {}
            should_include = bool(bundle_candidates) or bool(bundle_requirement.get("required")) or launcher_value == "llamafactory-cli"
            if not should_include:
                continue
        if field_name == "model_asset":
            bundle = assets.get("model") if isinstance(assets.get("model"), dict) else {}
            if not (bool((bundle.get("requirement") or {}).get("required")) or list(bundle.get("candidates") or [])):
                continue
        if field_name == "dataset_asset":
            bundle = assets.get("dataset") if isinstance(assets.get("dataset"), dict) else {}
            if not (bool((bundle.get("requirement") or {}).get("required")) or list(bundle.get("candidates") or [])):
                continue
        if field_name == "checkpoint_asset":
            bundle = assets.get("checkpoint") if isinstance(assets.get("checkpoint"), dict) else {}
            if not list(bundle.get("candidates") or []):
                continue
        sequence.append(dict(item))
    return sequence


def build_field_confirmation_step(
    scan: Dict[str, object],
    profile: Dict[str, object],
    field_name: str,
    step_number: int,
    total_steps: int,
) -> Dict[str, object]:
    definition = confirmation_definition(field_name)
    confirmed_fields = profile.get("confirmed_fields") if isinstance(profile.get("confirmed_fields"), dict) else {}
    field_item = confirmed_fields.get(field_name) if isinstance(confirmed_fields.get(field_name), dict) else {}
    recommended_value = field_item.get("value")

    if field_name == "runtime_environment":
        selected_environment = profile.get("selected_environment") or {}
        options = build_runtime_environment_options(scan)
        if isinstance(field_item, dict):
            recommended_value = field_item.get("value")
        else:
            recommended_value = selected_environment.get("id") if selected_environment else None
    else:
        candidate_key = str(definition.get("candidate_key"))
        if candidate_key == "cann_candidates":
            candidates = list(scan["cann"]["candidates"])
            options = build_numbered_options(ranked_candidates(candidates), allow_free_text=bool(definition.get("allow_free_text", True)))
        elif candidate_key.startswith("asset:"):
            asset_kind = candidate_key.split(":", 1)[1]
            options = build_asset_confirmation_options(asset_bundle(scan, asset_kind), allow_free_text=bool(definition.get("allow_free_text", True)))
        else:
            candidates = list(scan.get(candidate_key) or [])
            catalog_key = definition.get("catalog_key")
            if isinstance(catalog_key, str):
                candidates = merge_catalog_candidates(catalog_key, candidates)
            options = build_numbered_options(ranked_candidates(candidates), allow_free_text=bool(definition.get("allow_free_text", True)))

    for option in options:
        option["recommended"] = option.get("value") == recommended_value

    return {
        "field": field_name,
        "label": definition.get("label"),
        "prompt": definition.get("prompt"),
        "step_number": step_number,
        "total_steps": total_steps,
        "recommended_value": recommended_value,
        "allow_free_text": bool(definition.get("allow_free_text", True)),
        "manual_hint": definition.get("manual_hint"),
        "options": options,
    }


def build_confirmation_state(scan: Dict[str, object], profile: Dict[str, object]) -> Dict[str, object]:
    confirmed_fields = profile.get("confirmed_fields") if isinstance(profile.get("confirmed_fields"), dict) else {}
    sequence = active_confirmation_sequence(scan, profile)
    pending_fields = [item["field"] for item in sequence if not confirmation_field_is_confirmed(item["field"], confirmed_fields)]
    current_step_number = len(sequence) - len(pending_fields) + 1 if pending_fields else len(sequence)
    current_confirmation = build_field_confirmation_step(scan, profile, pending_fields[0], current_step_number, len(sequence)) if pending_fields else None
    return {
        "required": bool(pending_fields),
        "ready_for_validation": not pending_fields,
        "pending_fields": pending_fields,
        "gate_pending_fields": [field_name for field_name in VALIDATION_GATE_FIELDS if field_name in pending_fields],
        "current_confirmation": current_confirmation,
    }
