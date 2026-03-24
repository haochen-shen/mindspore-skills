---
description: Diagnose MindSpore and PTA (torch_npu) training and runtime failures by analyzing evidence, validating likely root causes, and emitting an actionable report
---

# Failure Agent

Diagnose training and runtime failures across MindSpore and PTA (PyTorch + torch_npu).

Load the `failure-agent` skill and follow its four-stage workflow.

## Typical Inputs

- full traceback or error log
- framework versions and backend/device details
- exact failing command and runtime context
- previous readiness snapshot if available
