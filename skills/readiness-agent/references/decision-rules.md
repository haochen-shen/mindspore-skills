# Readiness-Agent Decision Rules

## Target and Framework

- prefer explicit `target` and `framework_hint`
- otherwise infer from high-confidence workspace evidence inside the selected
  workspace only
- when `framework_hint` is absent, require user confirmation before running
  framework-specific checks or fixes
- if evidence is weak or conflicting, downgrade confidence instead of forcing a
  strong conclusion
- do not search sibling repos, home-directory projects, or bundled examples for
  missing workspace evidence
- if workspace evidence points to PTA, stay on PTA checks and do not probe
  MindSpore
- if workspace evidence points to MindSpore, stay on MindSpore checks and do
  not probe PTA
- use `mixed` only when the current workspace contains evidence for both

## Workspace Boundary

- treat the current workspace as the certification boundary
- only inspect workspace-local entry scripts, configs, assets, and virtual
  environments unless the user explicitly points to another path
- only select Python from explicit user input, a workspace-local virtual
  environment, or the current shell's already activated non-system virtual
  environment
- if no workspace-local virtual environment exists, reuse the current shell's
  activated non-system virtual environment before declaring Python missing
- do not scan unactivated global, user-level, shared, or system environment
  pools to discover a usable Python environment
- do not run broad environment inventory commands such as `conda env list`, and
  do not search common env roots such as Conda env warehouses, home-directory
  env collections, shared filesystems, or other non-workspace env pools
- external runtime directories may be resolved from environment variables when
  they represent CANN or Hugging Face state
- if the readiness entrypoint returns `BLOCKED`, stop and report that blocker
  instead of continuing with ad hoc shell-based host diagnosis outside the
  readiness workflow

## Runtime Threshold

- `runtime_smoke` is the minimum threshold for `READY`
- if `runtime_smoke` fails, do not emit `READY`
- explicit `task_smoke_cmd` is stronger evidence when present

## CANN Resolution

- treat an explicit `cann_path` as authoritative
- if an explicit `cann_path` is invalid or incompatible, return `BLOCKED`
- treat explicit Ascend runtime environment variables as authoritative runtime
  input
- if explicit Ascend runtime environment variables are invalid or incompatible,
  return `BLOCKED`
- before using an auto-detected installed CANN, require user confirmation
- when Ascend is required and no usable explicit CANN is present, `fix` may
  install a workspace-local managed CANN only after explicit user confirmation
- choose the latest compatible managed CANN from local driver and firmware facts
- when a managed CANN download is required, use Huawei's official CANN
  download service; only an explicit artifact URL override or a workspace-local
  cached package may bypass the official download path
- if driver or firmware facts are unresolved, do not guess a CANN version
- prefer a compatible workspace-local managed CANN over an incompatible active
  environment only when the user did not pass `cann_path` and did not provide
  explicit Ascend runtime environment variables and confirmed managed CANN
  installation

## Asset Rules

- local assets satisfy the requirement immediately
- explicit Hugging Face repo IDs may satisfy model or dataset requirements when
  the endpoint is reachable and the workflow can materialize the required asset
- missing entry scripts are only auto-repairable when a known bundled example
  recipe applies

## Final Question

After `READY` or `WARN`, ask whether to run the real model script now.
