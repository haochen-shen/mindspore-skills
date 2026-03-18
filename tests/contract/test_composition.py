"""Contract tests for skill composition graph.

Validates:
- composes references point to existing skill directories
- composition graph has no cycles (DAG)
- factory.card_types values are from canonical set
- skill.yaml name matches directory name
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
sys.path.insert(0, str(SKILLS_DIR / "_shared"))


def _load_skill_directories():
    """Return set of skill directory names (those with SKILL.md)."""
    return {
        p.name
        for p in SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    }


def _load_skills_with_yaml():
    """Return list of parsed skill.yaml dicts for skills that have one."""
    yaml = pytest.importorskip("yaml")
    skills = []
    for p in SKILLS_DIR.iterdir():
        yaml_path = p / "skill.yaml"
        if p.is_dir() and yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text())
            data["_dir_name"] = p.name
            skills.append(data)
    return skills


def test_composes_references_exist():
    """Every name in composes must be an existing skill directory."""
    all_dirs = _load_skill_directories()
    for skill in _load_skills_with_yaml():
        for ref in skill.get("composes", []):
            assert ref in all_dirs, (
                f"{skill['name']} composes '{ref}' but no "
                f"skills/{ref}/SKILL.md exists"
            )


def test_no_circular_composition():
    """Composition graph must be a DAG (no cycles)."""
    skills = _load_skills_with_yaml()
    adj = {s["name"]: s.get("composes", []) for s in skills}

    visited = set()
    in_stack = set()

    def dfs(node):
        if node in in_stack:
            return True  # cycle
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if dfs(neighbor):
                return True
        in_stack.discard(node)
        return False

    for name in adj:
        if dfs(name):
            pytest.fail(f"Circular composition detected involving '{name}'")


def test_factory_card_types_valid():
    """Factory card_types must be from the canonical set."""
    from factory.card_types import CARD_TYPES

    valid = set(CARD_TYPES.keys())
    for skill in _load_skills_with_yaml():
        for ct in skill.get("factory", {}).get("card_types", []):
            assert ct in valid, (
                f"{skill['name']} uses factory card_type '{ct}' "
                f"which is not in CARD_TYPES: {valid}"
            )


def test_skill_name_matches_directory():
    """skill.yaml name field must match its directory name."""
    for skill in _load_skills_with_yaml():
        assert skill["name"] == skill["_dir_name"], (
            f"skill.yaml name '{skill['name']}' does not match "
            f"directory name '{skill['_dir_name']}'"
        )
