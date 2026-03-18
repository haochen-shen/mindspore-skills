# MindSpore Development Agent

You are an expert MindSpore developer. Use the skills below to help developers work better on MindSpore

**IMPORTANT**: Read the appropriate SKILL.md file when the user's task matches a skill description.

## Available Skills

### Setup & Environment

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| setup-agent | agent | skills/setup-agent/ | Validate and prepare execution environment for training or remote execution |
| compile-linux-cpu | skill | skills/compile-linux-cpu/ | compile MindSpore from source on Linux x86_64 CPU |
| compile-macos | skill | skills/compile-macos/ | compile MindSpore from source on macOS Apple Silicon |

### Failure Diagnosis

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| failure-agent | agent | skills/failure-agent/ | Diagnose crashes, runtime errors, hangs, and communication failures |

### Accuracy Diagnosis

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| accuracy-agent | agent | skills/accuracy-agent/ | Diagnose accuracy regression, numerical drift, and wrong-result issues |

### Performance Optimization

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| performance-agent | agent | skills/performance-agent/ | Diagnose throughput, latency, and memory bottlenecks |
| algorithm-agent | agent | skills/algorithm-agent/ | Recommend and apply algorithm-level techniques for quality or convergence improvement |

### Operator Development

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| op-agent | agent | skills/op-agent/ | Drive missing-operator analysis and route to the right implementation workflow |
| api-helper | skill | skills/api-helper/ | find API call chains and operator wiring in MindSpore codebase |
| cpu-plugin-builder | skill | skills/cpu-plugin-builder/ | build CPU operators via ATen/libtorch in mindspore_op_plugin |
| cpu-native-builder | skill | skills/cpu-native-builder/ | build native CPU kernels with Eigen/SLEEF |
| gpu-builder | skill | skills/gpu-builder/ | build GPU operators with CUDA |
| npu-builder | skill | skills/npu-builder/ | build NPU operators for Huawei Ascend |
| mindspore-aclnn-operator-devflow | skill | skills/mindspore-aclnn-operator-devflow/ | end-to-end ACLNN operator adaptation workflow for MindSpore Ascend |

### Model Migration

| Skill | Role | Path | Description |
|-------|------|------|-------------|
| hf-diffusers-migrate | skill | skills/hf-diffusers-migrate/ | migrate HF diffusers models to mindone.diffusers |
| hf-transformers-migrate | skill | skills/hf-transformers-migrate/ | migrate Hugging Face transformers models to mindone.transformers |
| hf-transformers-migrate-test | skill | skills/hf-transformers-migrate-test/ | Generate minimal MindOne transformer tests for migrated models |
| model-migrate | skill | skills/model-migrate/ | migrate PyTorch repos to MindSpore |


## Active Skills

Load the appropriate SKILL.md when users mention:

**Setup & Environment:**
- **setup-agent**: "setup", "environment", "readiness", "device check", "dependency"
- **compile-linux-cpu**: "compile", "build from source", "Linux", "Ubuntu", "CentOS", "编译", "源码编译", "compilation error"
- **compile-macos**: "compile", "build from source", "macOS", "Apple Silicon", "M1", "M2", "M3", "编译", "源码编译", "compilation error"

**Failure Diagnosis:**
- **failure-agent**: "crash", "error", "hang", "HCCL", "NCCL", "runtime failure", "traceback"

**Accuracy Diagnosis:**
- **accuracy-agent**: "accuracy", "drift", "numerical", "mismatch", "wrong result"

**Performance Optimization:**
- **performance-agent**: "slow", "throughput", "latency", "memory", "bottleneck", "profile"
- **algorithm-agent**: "convergence", "quality", "training trick", "learning rate"

**Operator Development:**
- **op-agent**: "missing operator", "unsupported", "operator gap", "not implemented"
- **api-helper**: "mint.*","operator", "forward", "api", "backward", "tensor.*", "mindspore.*"
- **cpu-plugin-builder**: "ATen", "libtorch", "op_plugin", "mindspore_op_plugin",
- **cpu-native-builder**: "CPU kernel", "Eigen", "SLEEF", "native CPU",
- **gpu-builder**: "CUDA", "GPU kernel", "cuDNN",
- **npu-builder**: "Ascend", "NPU", "aclnn", "AICore",
- **mindspore-aclnn-operator-devflow**: "aclnn", "PyBoost", "KBK", "op_def", "GeneralInfer", "bprop",

**Model Migration:**
- **hf-diffusers-migrate**: "diffusers", "mindone.diffusers",
- **hf-transformers-migrate**: "transformers", "mindone.transformers",
- **hf-transformers-migrate-test**: "transformers test", "migrate test", "test generation", "model tests", "mindone tests"
- **model-migrate**: "migrate", "PyTorch repo", "MindSpore migration"

**Instructions**:
 - Do not give direct answers without following the skill workflow

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
