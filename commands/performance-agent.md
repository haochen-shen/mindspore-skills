---
description: Run an end-to-end performance workflow for MindSpore or torch_npu workloads on Ascend: collect profiler data when needed, build structured diagnosis artifacts, apply one copied optimization feature, rerun, and validate the measured gain
---

# Performance Agent

Run an end-to-end performance workflow in workloads that already run
successfully but are too slow, memory-heavy, or poorly utilized across
MindSpore and torch_npu.

Load the `performance-agent` skill and follow its deterministic five-stage
workflow. The product pipeline now prefers structured profiler summaries,
applies one copied optimization trial, reruns the workload, and emits reusable
report artifacts instead of relying on free-form diagnosis only.

## Typical Inputs

- runtime context and symptom description
- profiler trace root or exported profiler directory if available
- throughput, latency, memory, utilization, or communication symptoms
- earlier readiness snapshot if available
- optional before/after metric JSON for validation comparison
- optional output directory for structured artifacts such as `report.json`,
  `report.md`, `meta/performance-profile.json`, and
  `meta/performance-verdict.json`
