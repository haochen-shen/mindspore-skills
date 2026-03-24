---
description: Build framework operators through either custom-access integration or native-framework integration, then verify and deliver the resulting artifact
---

# Op Agent

Build a `torch` or `mindspore` operator from a workspace and delivery target.

Load the `op-agent` skill and follow its four-stage workflow:

1. operator analysis
2. method selection
3. implementation build
4. verification and report

## Typical Inputs

- working directory
- framework and backend when already known
- operator name
- preferred method if already decided
- delivery goal such as plugin or wheel
