---
description: Analyze a local single-machine training workspace, validate readiness before training, and emit a reusable snapshot and report
---

# Env Agent

Analyze the current training workspace before execution.

Load the `env-agent` skill and follow its four-stage workflow:

1. workspace analysis
2. compatibility validation
3. snapshot build
4. report build

## Typical Inputs

- code folder or working directory
- train config, model, dataset, or checkpoint paths if already known
- framework hints if the user already knows them
