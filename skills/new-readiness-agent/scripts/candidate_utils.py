#!/usr/bin/env python3
from typing import Dict, List, Optional


CATALOG_FIELD_OPTIONS = {
    "target": [
        ("training", "training"),
        ("inference", "inference"),
    ],
    "launcher": [
        ("python", "python"),
        ("bash", "bash"),
        ("torchrun", "torchrun"),
        ("accelerate", "accelerate"),
        ("deepspeed", "deepspeed"),
        ("msrun", "msrun"),
        ("llamafactory-cli", "llamafactory-cli"),
        ("make", "make"),
    ],
    "framework": [
        ("mindspore", "mindspore"),
        ("pta", "pta"),
        ("mixed", "mixed"),
    ],
}


def choose_top_candidate(items: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if not items:
        return None
    return max(items, key=lambda item: float(item.get("confidence") or 0.0))


def merge_catalog_candidates(field_name: str, detected_candidates: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen_values = {item.get("value") for item in detected_candidates}
    results = list(detected_candidates)
    for value, label in CATALOG_FIELD_OPTIONS.get(field_name, []):
        if value in seen_values:
            continue
        results.append(
            {
                "value": value,
                "label": label,
                "confidence": 0.18,
                "selection_source": "catalog",
            }
        )
    return results


def looks_like_local_path(value: str) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    if "/" in normalized or "\\" in normalized:
        return True
    if normalized.startswith("."):
        return True
    if ":" in normalized and not normalized.startswith(("hf_hub:", "hf_cache:", "script_managed_remote:", "local:")):
        return True
    return False


def ranked_candidates(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return sorted(items, key=lambda item: float(item.get("confidence") or 0.0), reverse=True)
