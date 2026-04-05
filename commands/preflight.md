---
description: Check whether the local workspace is ready to train or run inference
---

# Preflight

Use this as the top-level entrypoint for pre-run environment and workspace
validation.

Route internally to `readiness-agent`.

## What it checks

- Python and framework installation (MindSpore, PyTorch, torch_npu)
- CANN and driver versions
- NPU/GPU device availability
- Required dependencies and versions
- Training script and data path accessibility
- Common configuration issues

## Usage

```text
/preflight can I train qwen3 on this machine?
/preflight check if my environment is ready for MindSpore training
/preflight is this workspace set up for torch_npu inference?
```

If the user does not specify what they want to run, `readiness-agent` will
perform a general workspace check and report what is available and what is
missing.

## Execution Contract

- run all checks non-destructively (read-only, no installs)
- report a clear pass/fail summary with actionable next steps
- if the user asks to fix issues found, hand off to the appropriate agent
