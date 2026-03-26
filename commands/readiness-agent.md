description: Certify whether a local single-machine workspace is runnable for the intended training or inference task by discovering the execution target, validating dependency closure, optionally applying safe user-space remediation, revalidating affected checks, and emitting a reusable readiness report
---

# Readiness Agent

Certify whether the current local single-machine workspace is runnable for the
intended training or inference task.

Load the `readiness-agent` skill and follow its readiness certification
workflow:

1. selected Python resolution
2. execution target discovery
3. dependency closure and compatibility validation
4. blocker classification
5. optional safe user-space remediation and revalidation
6. readiness report build

## Typical Inputs

- code folder or working directory
- intended target or explicit entry script if already known
- training or inference config, model, dataset, or checkpoint paths if already
  known
- selected Python or selected environment root if already known
- explicit minimal smoke command if the user already knows a safe one
