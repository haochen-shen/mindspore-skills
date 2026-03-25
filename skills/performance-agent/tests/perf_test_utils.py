import json
from pathlib import Path


def write_sample_profiler_export(root: Path) -> Path:
    profiler_root = root / "worker_0_20260325_ascend_ms"
    ascend = profiler_root / "ASCEND_PROFILER_OUTPUT"
    cann = profiler_root / "PROF_0" / "mindstudio_profiler_output"
    ascend.mkdir(parents=True, exist_ok=True)
    cann.mkdir(parents=True, exist_ok=True)

    (profiler_root / "profiler_metadata.json").write_text("{}", encoding="utf-8")
    (profiler_root / "profiler_info_0.json").write_text("{}", encoding="utf-8")

    (ascend / "step_trace_time.csv").write_text(
        "\n".join(
            [
                "Step ID,DataTime(ms),ComputeTime(ms),CommunicationTime(ms),IdleGap(ms),StepTime(ms)",
                "1,6,28,44,8,86",
                "2,5,27,42,9,83",
                "3,7,29,46,7,89",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "kernel_details.csv").write_text(
        "\n".join(
            [
                "Kernel Name,Duration(ms)",
                "AllReduce,44",
                "MatMul,22",
                "LayerNorm,9",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "trace_view.json").write_text(
        json.dumps(
            {
                "events": [
                    {"name": "host_idle_gap", "duration_ms": 8},
                    {"name": "launch_overhead", "duration_ms": 12},
                    {"name": "graph_compile", "duration_ms": 6},
                    {"name": "AllReduce", "duration_ms": 44},
                ]
            }
        ),
        encoding="utf-8",
    )
    (ascend / "communication.json").write_text(
        json.dumps(
            {
                "communications": [
                    {"op_name": "AllReduce", "time_ms": 132, "count": 3, "size_mb": 256},
                    {"op_name": "AllGather", "time_ms": 24, "count": 3, "size_mb": 64},
                ]
            }
        ),
        encoding="utf-8",
    )
    (ascend / "communication_matrix.json").write_text(
        json.dumps(
            {
                "matrix": [
                    [120.0, 100.0],
                    [110.0, 95.0],
                ]
            }
        ),
        encoding="utf-8",
    )
    (ascend / "memory_record.csv").write_text(
        "\n".join(
            [
                "Timestamp,Peak Memory(MB)",
                "1,32768",
                "2,38912",
                "3,40960",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "operator_memory.csv").write_text(
        "\n".join(
            [
                "Operator Name,Peak Memory(MB)",
                "Attention,16384",
                "Embedding,8192",
                "LayerNorm,2048",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "npu_module_mem.csv").write_text(
        "\n".join(
            [
                "Module Name,Peak Memory(MB)",
                "encoder.block0,20480",
                "embedding,8192",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "dataset.csv").write_text(
        "\n".join(
            [
                "Queue Empty Percent,Wait Time(ms),Dataset Time(ms)",
                "28,14,18",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ascend / "minddata_pipeline_summary_0.json").write_text(
        json.dumps({"warning": "queue empty events observed", "queue_empty_percent": 28}),
        encoding="utf-8",
    )
    (cann / "op_summary_0.csv").write_text(
        "\n".join(
            [
                "Operator Name,Total Time(ms),Count",
                "AllReduce,132,3",
                "MatMul,66,3",
                "LayerNorm,27,3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return profiler_root


def write_validation_metrics(root: Path) -> tuple[Path, Path]:
    before = root / "before-metrics.json"
    after = root / "after-metrics.json"
    before.write_text(
        json.dumps(
            {
                "metrics": {
                    "throughput": 100.0,
                    "step_time": 86.0,
                    "communication_time": 44.0,
                    "peak_memory": 40960.0,
                }
            }
        ),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps(
            {
                "metrics": {
                    "throughput": 112.0,
                    "step_time": 78.0,
                    "communication_time": 31.0,
                    "peak_memory": 40192.0,
                }
            }
        ),
        encoding="utf-8",
    )
    return before, after
