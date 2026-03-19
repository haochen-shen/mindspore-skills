---
description: Diagnose and optimize Ascend/NPU throughput, latency, memory, and utilization bottlenecks for MindSpore and torch_npu with a profiler-first workflow
---

# Performance Agent

Diagnose performance bottlenecks in Ascend/NPU workloads that run correctly but
are too slow, memory-heavy, or poorly utilized across MindSpore and torch_npu.

Load the `performance-agent` skill and follow its profiler-first workflow.

## Typical Inputs

- training or inference command and runtime context
- `msprof` trace data if available
- throughput, latency, memory, utilization, or communication symptoms
