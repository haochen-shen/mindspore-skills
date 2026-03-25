import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perf_test_utils import write_sample_profiler_export, write_validation_metrics


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    script = SCRIPTS / script_name
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def test_locator_and_multidimensional_summaries_recover_profiler_context(tmp_path: Path):
    profiler_root = write_sample_profiler_export(tmp_path)
    locate_json = tmp_path / "locate.json"
    step_json = tmp_path / "step.json"
    comm_json = tmp_path / "comm.json"
    memory_json = tmp_path / "memory.json"
    input_json = tmp_path / "input.json"
    trace_gaps_json = tmp_path / "trace-gaps.json"

    run_script(
        "locate_profiler_output.py",
        "--working-dir",
        str(tmp_path),
        "--output-json",
        str(locate_json),
    )
    run_script(
        "summarize_step_breakdown.py",
        "--trace-root",
        str(profiler_root),
        "--output-json",
        str(step_json),
    )
    run_script(
        "summarize_communication.py",
        "--trace-root",
        str(profiler_root),
        "--output-json",
        str(comm_json),
    )
    run_script(
        "summarize_memory_pressure.py",
        "--trace-root",
        str(profiler_root),
        "--output-json",
        str(memory_json),
    )
    run_script(
        "summarize_input_pipeline.py",
        "--trace-root",
        str(profiler_root),
        "--output-json",
        str(input_json),
    )
    run_script(
        "summarize_trace_gaps.py",
        "--trace-root",
        str(profiler_root),
        "--output-json",
        str(trace_gaps_json),
    )

    locate = json.loads(locate_json.read_text(encoding="utf-8"))
    step = json.loads(step_json.read_text(encoding="utf-8"))
    communication = json.loads(comm_json.read_text(encoding="utf-8"))
    memory = json.loads(memory_json.read_text(encoding="utf-8"))
    input_summary = json.loads(input_json.read_text(encoding="utf-8"))
    trace_gaps = json.loads(trace_gaps_json.read_text(encoding="utf-8"))

    assert locate["selected_root"] == str(profiler_root)
    assert locate["confidence"] in {"strong", "moderate"}
    assert step["dominant_stage"]["name"] == "communication"
    assert communication["dominant_collective"]["name"] == "AllReduce"
    assert communication["communication_pressure"] == "high"
    assert memory["peak_memory_mb"] == 40960.0
    assert memory["top_operators"][0]["name"] == "Attention"
    assert input_summary["bottleneck_detected"] is True
    assert trace_gaps["dominant_category"]["name"] == "communication"


def test_profile_classifier_and_validation_comparison_produce_ranked_structured_outputs(tmp_path: Path):
    profiler_root = write_sample_profiler_export(tmp_path)
    before_json, after_json = write_validation_metrics(tmp_path)
    hotspot_json = tmp_path / "hotspot-summary.json"
    locate_json = tmp_path / "locate.json"
    step_json = tmp_path / "step.json"
    comm_json = tmp_path / "comm.json"
    memory_json = tmp_path / "memory.json"
    input_json = tmp_path / "input.json"
    trace_gaps_json = tmp_path / "trace-gaps.json"
    profile_json = tmp_path / "profile.json"
    bottlenecks_json = tmp_path / "bottlenecks.json"
    validation_json = tmp_path / "validation.json"

    run_script("locate_profiler_output.py", "--trace-path", str(profiler_root), "--output-json", str(locate_json))
    run_script("summarize_step_breakdown.py", "--trace-root", str(profiler_root), "--output-json", str(step_json))
    run_script("summarize_communication.py", "--trace-root", str(profiler_root), "--output-json", str(comm_json))
    run_script("summarize_memory_pressure.py", "--trace-root", str(profiler_root), "--output-json", str(memory_json))
    run_script("summarize_input_pipeline.py", "--trace-root", str(profiler_root), "--output-json", str(input_json))
    run_script("summarize_trace_gaps.py", "--trace-root", str(profiler_root), "--output-json", str(trace_gaps_json))
    run_script(
        "summarize_msprof_hotspots.py",
        "--input-dir",
        str(profiler_root),
        "--output-md",
        str(tmp_path / "hotspot-summary.md"),
        "--output-json",
        str(hotspot_json),
    )
    run_script(
        "build_performance_profile.py",
        "--working-dir",
        str(tmp_path),
        "--user-problem",
        "Distributed training is stable but throughput is low and allreduce dominates step time.",
        "--locate-json",
        str(locate_json),
        "--step-json",
        str(step_json),
        "--communication-json",
        str(comm_json),
        "--memory-json",
        str(memory_json),
        "--input-json",
        str(input_json),
        "--trace-gaps-json",
        str(trace_gaps_json),
        "--hotspot-json",
        str(hotspot_json),
        "--output-json",
        str(profile_json),
    )
    run_script(
        "classify_bottlenecks.py",
        "--profile-json",
        str(profile_json),
        "--step-json",
        str(step_json),
        "--communication-json",
        str(comm_json),
        "--memory-json",
        str(memory_json),
        "--input-json",
        str(input_json),
        "--trace-gaps-json",
        str(trace_gaps_json),
        "--hotspot-json",
        str(hotspot_json),
        "--output-json",
        str(bottlenecks_json),
    )
    run_script(
        "compare_validation_metrics.py",
        "--before-json",
        str(before_json),
        "--after-json",
        str(after_json),
        "--output-json",
        str(validation_json),
    )

    profile = json.loads(profile_json.read_text(encoding="utf-8"))
    bottlenecks = json.loads(bottlenecks_json.read_text(encoding="utf-8"))
    validation = json.loads(validation_json.read_text(encoding="utf-8"))

    assert profile["primary_symptom"] == "communication overhead"
    assert profile["confidence"] in {"strong", "moderate"}
    assert profile["available_artifacts"]["trace_gap_summary"] is True
    assert bottlenecks["primary_candidate"]["name"] == "communication"
    assert validation["overall_result"] == "improved"
