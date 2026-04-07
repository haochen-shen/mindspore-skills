# Readiness-Agent Env-Fix Policy

`fix` mode is limited to safe user-space changes.

Allowed actions:

- install `uv` into the user environment when needed
- create or repair a workspace-local environment such as `.venv`
- install missing framework or runtime packages into the selected workspace env
  or the current shell's activated non-system virtual environment
- install a workspace-local CANN package inside the current workspace under
  `<working_dir>/cann/<version>/` after explicit user confirmation; the
  managed CANN install path uses the official Toolkit + ops run packages and
  keeps both installs inside the workspace-local target path, using Huawei's
  official CANN download service when a package download is needed unless the
  user provided an explicit artifact URL or the workspace already caches the
  package
- scaffold a bundled example entry script for a known recipe
- download explicitly declared model or dataset assets when they are required by
  the current readiness target

Disallowed actions:

- modify driver, firmware, or system-level CANN
- mutate system Python
- scan unactivated global, user-level, shared, or system Python environment
  pools in order to find a usable interpreter
- activate or switch into an arbitrary non-workspace environment that was not
  explicitly selected and is not already active in the current shell
- replace an explicit `cann_path` or explicit Ascend runtime environment
  variables with another CANN path
- auto-select a detected installed CANN without user confirmation
- run framework-specific checks or fixes before the user confirmed the
  framework when `framework_hint` was not provided
- continue with ad hoc shell-based host diagnosis after the readiness entrypoint
  already returned `BLOCKED`
- rewrite user model logic to make smoke pass
- make distributed or cluster-level environment changes

Every successful fix must be followed by revalidation of the affected scopes
before final certification.
