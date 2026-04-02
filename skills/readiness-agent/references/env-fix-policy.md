# Readiness-Agent Env-Fix Policy

`fix` mode is limited to safe user-space changes.

Allowed actions:

- install `uv` into the user environment when needed
- create or repair a workspace-local environment such as `.venv`
- install missing framework or runtime packages into the selected env
- install a workspace-local CANN package inside the current workspace under
  `<working_dir>/cann/<version>/` after explicit user confirmation
- scaffold a bundled example entry script for a known recipe
- download explicitly declared model or dataset assets when they are required by
  the current readiness target

Disallowed actions:

- modify driver, firmware, or system-level CANN
- mutate system Python
- replace an explicit `cann_path` or explicit Ascend runtime environment
  variables with another CANN path
- auto-select a detected installed CANN without user confirmation
- rewrite user model logic to make smoke pass
- make distributed or cluster-level environment changes

Every successful fix must be followed by revalidation of the affected scopes
before final certification.
