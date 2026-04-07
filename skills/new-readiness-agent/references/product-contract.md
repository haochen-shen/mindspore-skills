# New-Readiness-Agent Product Contract

`new-readiness-agent` has one user-visible responsibility:

- certify whether the selected local single-machine workspace can start the
  intended training or inference workflow now

This skill is strictly read-only. It does not fix the environment, install
packages, or launch the real workload.

The final user-visible result must contain:

- `status`
- `can_run`
- `target`
- `summary`
- `missing_items`
- `warnings`
- `next_action`

The internal verdict must preserve:

- detected candidates for target, launcher, framework, and environment
- selected final values and their sources
- near-launch validation checks
- environment candidates and ranking
- readiness lock and confirmation form references
- workspace latest cache references

