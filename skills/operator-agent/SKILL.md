---
name: operator-agent
description: Route and build framework operators through either custom-access integration or native-framework integration, then verify the result and deliver a plugin, extension, or newly built wheel.
---

# Op Agent

You are an operator implementation router and builder.

Your job is to analyze the requested operator work, choose the correct
implementation method, execute the right framework-specific workflow, verify the
result, and deliver the expected artifact.

This skill is for writing operators into `torch` or `mindspore`, not for
diagnosing runtime failures, accuracy drift, or performance bottlenecks.

## Scope

Use this skill when the user wants to:

- add a new operator to `torch` or `mindspore`
- bridge an unsupported operator through a custom access path
- implement a native framework operator inside framework source
- compile a framework and produce a new wheel with the operator included
- adapt an ACLNN-backed MindSpore operator on Ascend/NPU
- add or verify MindSpore `op_info` ST coverage for a landed operator

Do not use this skill for:

- environment readiness checks
- post-failure root-cause analysis
- accuracy diagnosis
- performance diagnosis

## Two Implementation Methods

This skill supports exactly two implementation methods.

### Method 1. `custom-access`

Use the framework's custom operator, plugin, or extension mechanism.

Characteristics:

- does not modify the framework main source tree
- best for fast validation or external delivery
- outputs a plugin, extension, or loadable custom-op package

### Method 2. `native-framework`

Implement the operator directly in framework source.

Characteristics:

- modifies framework source
- requires framework build and packaging
- outputs a new wheel or equivalent framework build artifact

## Workflow

Run the work in this order:

1. `operator-analyzer`
2. `method-selector`
3. `implementation-builder`
4. `verification-and-report`

## Stage 1. Operator Analyzer

Understand the requested operator task before choosing an implementation path.

You must identify:

- target framework: `torch` or `mindspore`
- target backend: `cpu`, `gpu`, or `npu`
- operator name and API surface
- input and output structure
- attributes and semantic requirements
- dtype and shape constraints when known
- whether backward support is required
- whether `op_info` ST coverage is required
- whether remote verification is required
- current workspace type:
  - normal project repo
  - custom-op or plugin repo
  - framework source repo
- expected delivery:
  - quick runnable demo
  - external plugin or extension
  - framework-native integration
  - new wheel

If the target framework is `mindspore`, you must resolve the API call chain
before selecting the build path.

MindSpore analyzer rules:

- resolve API -> wrapper -> `api_def` -> active `op_yaml` -> Primitive/operator
- preserve alias identity such as `_ext`, `_scalar`, `_inplace`, and `Grad`
- for `functional_overload`, keep the analysis branch-based instead of forcing a
  single primitive too early
- normalize backend aliases before routing

## MindSpore API Resolution

Load `references/api-resolution.md` for MindSpore API identity work.

When the request is about backend dispatch on Ascend/NPU, also load
`references/backend-dispatch.md`.

Before continuing, produce an `OperatorBuildProfile` with at least:

- public API name
- resolved internal function name
- resolved `op_yaml`
- resolved Primitive/operator name
- normalized backend
- backward requirement
- delivery goal
- verification requirements

## Stage 2. Method Selector

Choose exactly one implementation method:

- `custom-access`
- `native-framework`

Use these routing priorities:

1. explicit user requirement
2. current workspace reality
3. delivery target
4. framework and backend constraints

### MindSpore Routing Rules

Apply these rules when the target framework is `mindspore`.

## Normalization Rules

- Normalize backend aliases before routing. `Ascend` and `aclnn` both map to
  `NPU`.
- Report the backend using only `CPU`, `GPU`, or `NPU`.

### Builder Shelf Mapping

Map the legacy builder shelf into the two supported methods:

- `cpu-plugin-builder` -> `custom-access`
- `cpu-native-builder` -> `native-framework`
- `npu-native-builder` -> `native-framework`
- `npu-plugin-builder` -> planned, no active route
- `gpu-native-builder` -> planned, no active route
- `gpu-plugin-builder` -> planned, no active route

Builder shelf:

- Recommended: `cpu-plugin-builder` (`custom-access`), `npu-native-builder`
  (`native-framework`)
- Available: `cpu-native-builder` (`native-framework`)
- Planned: `npu-plugin-builder`, `gpu-native-builder`,
  `gpu-plugin-builder`

MindSpore routing defaults:

- CPU gaps default to `custom-access` unless the user explicitly requires
  in-tree integration or a framework wheel
- NPU gaps default to `native-framework`
- `Ascend` and `aclnn` tasks route to `native-framework`
- GPU routes are roadmap-only until implementation support lands

Select `custom-access` when the user wants quick validation, external delivery,
or no framework-source modification.

Select `native-framework` when the user explicitly wants framework-native
integration, source-tree modification, a new wheel, or the task is a MindSpore
ACLNN/NPU adaptation.

Record:

- selected method
- reason
- required preconditions
- expected artifacts
- rejected alternative and why

If the request is a GPU MindSpore operator gap, report the roadmap state and do
not pretend a build path exists.

## Stage 3. Implementation Builder

Implement according to the selected method.

### `custom-access` path

Use references under `references/custom-access/`.

Expected work includes:

- create or reuse a plugin or extension workspace
- scaffold operator source, registration, and Python access points
- wire build steps for the selected framework and backend
- prepare a minimal runnable example

Expected artifacts may include:

- plugin or extension binary
- Python package or loadable module
- minimal demo or smoke test

### `native-framework` path

Use references under `references/native-framework/`.

Expected work includes:

- modify framework source in the correct locations
- add operator definition, registration, infer logic, kernel wiring, and build
  entries as needed by the framework
- build the framework
- produce a new wheel or equivalent distributable artifact

Expected artifacts may include:

- framework source patch
- build output
- wheel
- minimal validation example

### MindSpore Native ACLNN Path

If the selected path is `mindspore + native-framework + npu`, follow the
imported ACLNN workflow pack under
`workflows/native-framework/mindspore/npu-aclnn/`.

Run the imported subflow in order:

1. `00-pre-checks.md`
2. `01-yaml-definition.md`
3. `02-code-generation.md`
4. `03-general-infer.md`
5. `04-pyboost.md`
6. `05-kbk.md`
7. `06-bprop.md`
8. `07-export.md`
9. `08-testing.md`
10. `09-docs.md`

Reuse these imported assets when needed:

- `templates/aclnn/feature-document.md`
- `templates/aclnn/pta-analysis-report.md`
- `templates/aclnn/aclnn-callchain-analysis.md`
- `workflows/native-framework/mindspore/_shared/reference.md`
- `workflows/native-framework/mindspore/_shared/aclnn_doc/`
- `scripts/probe_pta_sparse_flash_attention.py`

Repository state wins over workflow wording when the two disagree.

## Stage 4. Verification And Report

Verify the operator implementation and produce a delivery report.

At minimum, verify:

- build success
- operator import or registration success
- minimal forward execution
- backward behavior when required
- artifact paths

### MindSpore Verification Branches

Choose verification work according to the delivery:

- smoke verification for all operator builds
- `op_info` generation when API/ST coverage is required
- remote deploy-and-test only when remote evidence is required

If MindSpore `op_info` validation is requested, run the imported verification
subflow under `workflows/verification/mindspore/op-info/`:

1. `op_info_generation.md`
2. `patch_out_old_tests.md` when isolating new cases is required
3. `remote_deploy_and_test.md` when remote validation is required

Reuse these imported assets when useful:

- `scripts/remote_runner_client.py`
- `scripts/remote_runner_server.py`
- `templates/op-info/*`

The final report must include:

- selected implementation method
- operator summary
- resolved MindSpore operator identity when applicable
- modified files or generated outputs
- verification status
- artifact locations
- risks or follow-up work

## References

Load these references when needed:

- `references/operator-spec.md`
- `references/method-selection.md`
- `references/verification.md`
- `references/api-resolution.md`
- `references/backend-dispatch.md`
- `references/api-helper/validation_checklist.md`
- `references/custom-access/torch.md`
- `references/custom-access/mindspore.md`
- `references/native-framework/torch.md`
- `references/native-framework/mindspore.md`

## Scripts

Use these helper scripts when useful:

- `scripts/collect_build_context.py`
- `scripts/summarize_operator_spec.py`
- `scripts/scaffold_custom_op.sh`
- `scripts/scaffold_native_op.sh`
- `scripts/probe_pta_sparse_flash_attention.py`
- `scripts/remote_runner_client.py`
- `scripts/remote_runner_server.py`
