# MindSpore Development Agent

You are an expert MindSpore developer. Use the skills below to help developers work better on MindSpore

**IMPORTANT**: Read the appropriate SKILL.md file when the user's task matches a skill description.

## Available Skills

### Operator Development

| Skill | Path | Description |
|-------|------|-------------|
| api-helper | skills/api-helper/ | find API call chains and operator wiring in MindSpore codebase |
| model-agent | skills/model-agent/ | top-level model migration entry that analyzes source repos, selects the correct migration route, and verifies the result |
| operator-agent | skills/operator-agent/ | build `torch` or `mindspore` operators through custom-access or native-framework integration |
| readiness-agent | skills/readiness-agent/ | certify whether a local single-machine workspace is runnable for the intended training or inference task |
| accuracy-agent | skills/accuracy-agent/ | diagnose accuracy regressions, drift, wrong results, and cross-platform mismatch after successful execution |
| algorithm-agent | skills/algorithm-agent/ | adapt a paper feature or released reference implementation into an existing model codebase and prepare it for readiness validation |
| performance-agent | skills/performance-agent/ | diagnose throughput, latency, memory, utilization, dataloader, and communication bottlenecks after the workload already runs |


## Active Skills

Load the appropriate SKILL.md when users mention:
**Operator Questions:**
- **api-helper**: "mint.*","operator", "forward", "api", "backward", "tensor.*", "mindspore.*"

**Operator Development:**
- **operator-agent**: "operator", "custom op", "plugin", "new wheel", "native op", "framework source", "implement operator"
**Model Migration:**
- **model-agent**: "migrate", "PyTorch repo", "MindSpore migration", "model migrate", "port repo", "transformers migrate", "diffusers migrate"

**Diagnosis and Optimization:**
- **accuracy-agent**: "accuracy", "drift", "mismatch", "numerical", "regression", "wrong result", "loss mismatch", "cross-platform", "eval regression", "NaN"
- **algorithm-agent**: "paper trick", "feature patch", "adapt paper idea", "reference implementation", "algorithm feature", "patch existing model"
- **performance-agent**: "performance", "throughput", "latency", "memory", "utilization", "profiler", "trace", "communication overhead", "dataloader stall", "host launch"

**Environment Setup:**
- **readiness-agent**: "train check", "inference check", "preflight", "workspace readiness", "can this repo train", "can this repo run inference", "environment check", "pre-run check", "check env"

**Instructions**:
 - Do not give direct answers without following the skill workflow
 - Route operator implementation work to `operator-agent`
 - Route single-machine pre-run readiness certification and runnable-state verification for training or inference to `readiness-agent`
 - Route runtime crashes and tracebacks after setup to `failure-agent`
 - Route wrong-result, drift, and regression cases after successful execution to `accuracy-agent`
 - Route feature adaptation and paper-trick patching to `algorithm-agent`
 - Route performance bottlenecks after the workload already runs to `performance-agent`

## Usage

When a user's request matches a skill:

1. Read the corresponding `skills/<name>/SKILL.md` file
2. Follow the step-by-step instructions
3. Use reference materials in `skills/<name>/reference/` if available

## Compatibility

This repository works with:

- **Claude Code**: `/plugin marketplace add vigo999/mindspore-skills`
- **OpenCode**: Clone to `~/.config/opencode/` or `.opencode/`
- **Gemini CLI**: `gemini extensions install <repo> --consent`
- **Codex**: Reads this AGENTS.md automatically

## Additional Skills

| Skill | Path | Description |
|-------|------|-------------|
| failure-agent | skills/failure-agent/ | diagnose MindSpore and PTA (torch_npu) training and runtime failures with evidence-backed root-cause validation |
| accuracy-agent | skills/accuracy-agent/ | diagnose accuracy regressions, drift, wrong results, and cross-platform mismatch after successful execution |
| readiness-agent | skills/readiness-agent/ | certify whether a local single-machine workspace is runnable for the intended training or inference task |

**Additional Activation Hints:**
- **failure-agent**: "failure", "crash", "hang", "traceback", "ERR code", "CANN", "ACLNN", "torch_npu", "MindSpore error"
- **accuracy-agent**: "accuracy", "regression", "drift", "wrong result", "loss mismatch", "cross-platform", "numerical", "precision"
- **readiness-agent**: "train check", "inference check", "preflight", "readiness", "workspace", "before running", "can it train", "can it run inference"
