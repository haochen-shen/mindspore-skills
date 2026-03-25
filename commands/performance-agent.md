---
description: Diagnose throughput, latency, memory, utilization, dataloader, and communication bottlenecks after a MindSpore or torch_npu workload already runs
---

# Performance Agent

Diagnose performance bottlenecks in workloads that already run successfully but
are too slow, memory-heavy, or poorly utilized across MindSpore and torch_npu.

Load the `performance-agent` skill and follow its deterministic four-stage
workflow. The product pipeline now prefers structured profiler summaries and
emits reusable report artifacts instead of relying on free-form diagnosis only.

## Typical Inputs

- runtime context and symptom description
- profiler trace root or exported profiler directory if available
- throughput, latency, memory, utilization, or communication symptoms
- earlier readiness snapshot if available
- optional before/after metric JSON for validation comparison
- optional output directory for structured artifacts such as `report.json`,
  `report.md`, `meta/performance-profile.json`, and
  `meta/performance-verdict.json`
