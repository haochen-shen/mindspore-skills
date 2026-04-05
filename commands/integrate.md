---
description: Integrate algorithm features or operators into an existing model codebase
---

# Integrate

Use this as the top-level entrypoint for adding new algorithm features or
operators into an existing model codebase.

Do lightweight deterministic routing first, then load exactly one specialist
skill:

- `algorithm-agent`
- `operator-agent`

## Routing Rules

Classify from the user's wording and any directly visible evidence:

- algorithm keywords:
  - feature
  - paper
  - technique
  - attention
  - MHC
  - MoE
  - LoRA
  - adapt
  - integrate
  - add to model
- operator keywords:
  - operator
  - op
  - kernel
  - custom op
  - op_info
  - ACLNN
  - torch op
  - mindspore op

## Routing Decision

- if the task is about integrating a paper feature, algorithm change, or model
  capability into an existing codebase, load `algorithm-agent`
- if the task is about building, registering, or verifying a framework operator,
  load `operator-agent`

If classification is ambiguous, ask the user to choose exactly one:

1. integrate an algorithm feature into a model
2. build or register a framework operator

## Execution Contract

After choosing the specialist skill:

- analyze the source (paper, reference implementation, or user description)
- present an integration plan with expected changes
- wait for user confirmation before applying anything
- apply changes incrementally with verification at each step
- run tests and report results

## Usage

```text
/integrate add MHC feature into Qwen3 model
/integrate implement a custom fused attention operator for MindSpore
/integrate port this LoRA technique from the paper into our training script
```

If the user does not specify what they want to integrate, ask for the source
(paper, repo, or description) before routing.
