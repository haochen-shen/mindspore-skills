from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"


def test_behavior_rules_require_running_workload_and_single_bottleneck_focus():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "Confirm that the workload already runs before doing bottleneck analysis." in text
    assert "Prefer real performance evidence over broad upfront guesswork." in text
    assert "Identify one dominant bottleneck before suggesting multiple changes." in text
    assert "Optimize one dominant bottleneck at a time." in text
    assert "Do not claim an optimization worked until the user verifies it." in text


def test_performance_profile_and_bottleneck_validation_are_present():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "Build a `PerformanceProfile`" in text
    assert "Return ranked bottleneck candidates with:" in text
    assert "- confidence" in text
    assert "- evidence" in text
    assert "- validation checks" in text
    assert "- optimization hints" in text


def test_references_and_scripts_are_declared():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "`references/perf-validation.md`" in text
    assert "`scripts/find_run_context.py`" in text
    assert "`scripts/collect_msprof.sh`" in text
    assert "`scripts/summarize_msprof_hotspots.py`" in text
