#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
COMMANDS_DIR = ROOT / "commands"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
GEMINI = ROOT / "gemini-extension.json"
SCHEMA = ROOT / "skills" / "_shared" / "contract" / "skill.schema.json"

# Commands that are routers only and do not require a skill.
ROUTER_COMMANDS = {
    "migrate",
    "hf-migrate",
    "diagnose",
    "optimize",
    "setup",
}

# Canonical factory card types (keep aligned with _shared/factory/card_types.py)
VALID_CARD_TYPES = {"known_failure", "operator", "model", "trick"}


def load_skills():
    skills = set()
    for path in SKILLS_DIR.iterdir():
        if path.is_dir() and (path / "SKILL.md").exists():
            skills.add(path.name)
    return skills


def load_commands():
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def load_skill_yamls():
    """Load skill.yaml manifests for skills that have them."""
    manifests = {}
    try:
        import yaml
    except ImportError:
        return manifests
    for path in SKILLS_DIR.iterdir():
        yaml_path = path / "skill.yaml"
        if path.is_dir() and yaml_path.exists():
            manifests[path.name] = yaml.safe_load(yaml_path.read_text())
    return manifests


def parse_agents_skills():
    skills = set()
    if not AGENTS.exists():
        return skills
    for line in AGENTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "|" in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if not cols or not cols[0]:
                continue
            if cols[0] == "Skill":
                continue
            if set(cols[0]) <= {"-"}:
                continue
            skills.add(cols[0])
    return skills


def parse_readme_skills():
    skills = set()
    if not README.exists():
        return skills
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|")
    for line in README.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            token = match.group(1)
            if not token.startswith("/"):
                skills.add(token)
    return skills


def parse_readme_commands():
    commands = set()
    if not README.exists():
        return commands
    pattern = re.compile(r"^\|\s*`/([^`]+)`\s*\|")
    for line in README.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            commands.add(match.group(1))
    return commands


def parse_gemini_skills():
    skills = set()
    if not GEMINI.exists():
        return skills
    data = json.loads(GEMINI.read_text(encoding="utf-8"))
    for item in data.get("skills", []):
        name = item.get("name")
        if name:
            skills.add(name)
    return skills


def check_frontmatter_names():
    """Check SKILL.md frontmatter name matches directory name."""
    issues = []
    pattern = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
    for path in SKILLS_DIR.iterdir():
        skill_md = path / "SKILL.md"
        if not path.is_dir() or not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        match = pattern.match(text)
        if not match:
            continue
        try:
            import yaml
            fm = yaml.safe_load(match.group(1))
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue
        fm_name = fm.get("name")
        if fm_name and fm_name != path.name:
            issues.append(f"{path.name} (frontmatter says '{fm_name}')")
    return issues


def check_skill_yaml_schema(manifests):
    """Validate skill.yaml files against skill.schema.json."""
    issues = []
    try:
        import jsonschema
    except ImportError:
        return issues
    if not SCHEMA.exists():
        return issues
    schema = json.loads(SCHEMA.read_text())
    for name, manifest in manifests.items():
        try:
            jsonschema.validate(instance=manifest, schema=schema)
        except jsonschema.ValidationError as e:
            issues.append(f"{name}: {e.message}")
    return issues


def check_composes_references(manifests, all_skill_dirs):
    """Verify composes references point to existing skill directories."""
    issues = []
    for name, manifest in manifests.items():
        for ref in manifest.get("composes", []):
            if ref not in all_skill_dirs:
                issues.append(f"{name} composes unknown skill: {ref}")
    return issues


def check_factory_card_types(manifests):
    """Verify factory card_types are from the canonical set."""
    issues = []
    for name, manifest in manifests.items():
        factory = manifest.get("factory", {})
        for ct in factory.get("card_types", []):
            if ct not in VALID_CARD_TYPES:
                issues.append(f"{name} has unknown card_type: {ct}")
    return issues


def main():
    skills = load_skills()
    commands = load_commands()
    agents_skills = parse_agents_skills()
    readme_skills = parse_readme_skills()
    readme_commands = parse_readme_commands()
    gemini_skills = parse_gemini_skills()
    manifests = load_skill_yamls()

    issues = []

    missing_commands = sorted(skills - commands)
    if missing_commands:
        issues.append(("skills_missing_commands", missing_commands))

    extra_commands = sorted((commands - skills) - ROUTER_COMMANDS)
    if extra_commands:
        issues.append(("commands_without_skills", extra_commands))

    missing_agents = sorted(skills - agents_skills)
    if missing_agents:
        issues.append(("skills_missing_in_agents", missing_agents))

    extra_agents = sorted(agents_skills - skills)
    if extra_agents:
        issues.append(("agents_extra_skills", extra_agents))

    missing_readme_skills = sorted(skills - readme_skills)
    if missing_readme_skills:
        issues.append(("skills_missing_in_readme", missing_readme_skills))

    extra_readme_skills = sorted(readme_skills - skills)
    if extra_readme_skills:
        issues.append(("readme_extra_skills", extra_readme_skills))

    missing_readme_commands = sorted(commands - readme_commands)
    if missing_readme_commands:
        issues.append(("commands_missing_in_readme", missing_readme_commands))

    extra_readme_commands = sorted(readme_commands - commands)
    if extra_readme_commands:
        issues.append(("readme_extra_commands", extra_readme_commands))

    missing_gemini = sorted(skills - gemini_skills)
    if missing_gemini:
        issues.append(("skills_missing_in_gemini", missing_gemini))

    extra_gemini = sorted(gemini_skills - skills)
    if extra_gemini:
        issues.append(("gemini_extra_skills", extra_gemini))

    # --- New v1.1.0 checks ---

    fm_issues = check_frontmatter_names()
    if fm_issues:
        issues.append(("frontmatter_name_mismatch", fm_issues))

    schema_issues = check_skill_yaml_schema(manifests)
    if schema_issues:
        issues.append(("skill_yaml_schema_errors", schema_issues))

    compose_issues = check_composes_references(manifests, skills)
    if compose_issues:
        issues.append(("composes_invalid_references", compose_issues))

    card_issues = check_factory_card_types(manifests)
    if card_issues:
        issues.append(("factory_invalid_card_types", card_issues))

    if issues:
        print("Consistency issues found:")
        for key, values in issues:
            print(f"- {key}: {', '.join(values)}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
