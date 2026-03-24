# MindSpore Development Agent

You are an expert MindSpore developer. Use the skills below to help developers work better on MindSpore

**IMPORTANT**: Read the appropriate SKILL.md file when the user's task matches a skill description.

## Available Skills

### Operator Development

| Skill | Path | Description |
|-------|------|-------------|
| api-helper | skills/api-helper/ | find API call chains and operator wiring in MindSpore codebase |
| cpu-plugin-builder | skills/cpu-plugin-builder/ | build CPU operators via ATen/libtorch in mindspore_op_plugin |
| cpu-native-builder | skills/cpu-native-builder/ | build native CPU kernels with Eigen/SLEEF |
| gpu-builder | skills/gpu-builder/ | build GPU operators with CUDA |
| npu-builder | skills/npu-builder/ | build NPU operators for Huawei Ascend |
| mindspore-aclnn-operator-devflow | skills/mindspore-aclnn-operator-devflow/ | end-to-end ACLNN operator adaptation workflow for MindSpore Ascend |
| hf-diffusers-migrate | skills/hf-diffusers-migrate/ | migrate HF diffusers models to mindone.diffusers |
| hf-transformers-migrate | skills/hf-transformers-migrate/ | migrate Hugging Face transformers models to mindone.transformers |
| hf-transformers-migrate-test | skills/hf-transformers-migrate-test/ | Generate minimal MindOne transformer tests for migrated models |
| model-migrate | skills/model-migrate/ | top-level model migration entry that analyzes source repos, selects the correct migration route, and verifies the result |
| op-agent | skills/op-agent/ | build `torch` or `mindspore` operators through custom-access or native-framework integration |
| env-agent | skills/env-agent/ | analyze local single-machine training workspaces and report pre-run readiness |
| accuracy-agent | skills/accuracy-agent/ | diagnose accuracy regressions, drift, wrong results, and cross-platform mismatch after successful execution |
| performance-agent | skills/performance-agent/ | diagnose throughput, latency, memory, utilization, dataloader, and communication bottlenecks after the workload already runs |
| setup-agent | skills/setup-agent/ | validate local Ascend runtime readiness, uv environment selection, and model dependency installation for MindSpore or torch_npu |


## Active Skills

Load the appropriate SKILL.md when users mention:
**Operator Questions:**
- **api-helper**: "mint.*","operator", "forward", "api", "backward", "tensor.*", "mindspore.*"

**Operator Development:**
- **op-agent**: "operator", "custom op", "plugin", "new wheel", "native op", "framework source", "写算子"
- **cpu-plugin-builder**: "ATen", "libtorch", "op_plugin", "mindspore_op_plugin",
- **cpu-native-builder**: "CPU kernel", "Eigen", "SLEEF", "native CPU",
- **gpu-builder**: "CUDA", "GPU kernel", "cuDNN",
- **npu-builder**: "Ascend", "NPU", "aclnn", "AICore",
- **mindspore-aclnn-operator-devflow**: "aclnn", "PyBoost", "KBK", "op_def", "GeneralInfer", "bprop",

**Model Migration:**
- **hf-diffusers-migrate**: "diffusers", "mindone.diffusers",
- **hf-transformers-migrate**: "transformers", "mindone.transformers",
- **hf-transformers-migrate-test**: "transformers test", "migrate test", "test generation", "model tests", "mindone tests"
- **model-migrate**: "migrate", "PyTorch repo", "MindSpore migration", "model migrate", "port repo"

**Diagnosis and Optimization:**
- **accuracy-agent**: "accuracy", "drift", "mismatch", "numerical", "regression", "wrong result", "loss mismatch", "cross-platform", "eval regression", "NaN"
- **performance-agent**: "performance", "throughput", "latency", "memory", "utilization", "profiler", "trace", "communication overhead", "dataloader stall", "host launch"

**Environment Setup:**
- **env-agent**: "train check", "preflight", "workspace readiness", "can this repo train", "环境检查", "训练前检查", "check env"
- **setup-agent**: "环境检查", "setup", "Ascend", "NPU", "CANN", "driver", "torch_npu", "uv", "模型依赖", "环境变量", "npu-smi"

**Instructions**:
 - Do not give direct answers without following the skill workflow
 - Route operator implementation work to `op-agent`
 - Route training workspace analysis, pre-run readiness, and environment snapshots to `env-agent`
 - Route environment repair, package remediation, and uv setup to `setup-agent`
 - Route runtime crashes and tracebacks after setup to `failure-agent`
 - Route wrong-result, drift, and regression cases after successful execution to `accuracy-agent`
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
| env-agent | skills/env-agent/ | analyze local training workspaces and validate single-machine pre-run readiness |

**Additional Activation Hints:**
- **failure-agent**: "failure", "crash", "hang", "traceback", "ERR code", "CANN", "ACLNN", "torch_npu", "MindSpore error"
- **accuracy-agent**: "accuracy", "regression", "drift", "wrong result", "loss mismatch", "cross-platform", "数值", "精度"
- **env-agent**: "train check", "preflight", "readiness", "workspace", "训练前", "检查能不能训"
