# Readiness Agent Architecture Draft

## Goal

`readiness-agent` should answer one question:

- Can this workspace run the intended training or inference task now?

It should do four things, and only these four things:

1. Resolve the intended target.
2. Probe the environment and required assets.
3. Repair deterministic blockers inside safe user space.
4. Revalidate and report the result.

It is not a generic certification platform, and it should not expose its
internal helper choreography as the product.

## Product Contract

The final user-facing answer should always reduce to:

- can it run
- what is missing
- what was fixed
- what should happen next

The task under evaluation is always a specific target, not the machine in
general.

## Hard Constraints

- `pip` installs must use the Tsinghua mirror first and only fall back to the
  Aliyun mirror.
- Hugging Face downloads must explicitly use a mirror endpoint via
  `HF_ENDPOINT`, defaulting to `https://hf-mirror.com`.
- Never mutate driver, firmware, CANN, or system Python.
- Never silently fall back to system Python when a workspace-local environment
  is missing.
- Training should default to PTA unless the user explicitly asks for
  MindSpore.
- Missing required assets must block readiness.
- When `model` or `dataset` is missing and the source is known, `fix` may
  download it from Hugging Face.
- When `script` is missing, use this order:
  1. existing workspace script
  2. known recipe/template
  3. agent-generated script only after explicit user confirmation
  4. otherwise remain `BLOCKED`

## Target Model

The agent should reason about a single `ReadinessState` object with these core
fields:

- `working_dir`
- `mode`
- `target_type`
- `framework`
- `selected_python`
- `selected_env_root`
- `cann_selection`
- `required_assets`
- `missing_assets`
- `env_blockers`
- `asset_blockers`
- `warnings`
- `fixes_applied`
- `revalidated`
- `status`
- `next_action`

The state should be passed in memory wherever practical. JSON files are an
implementation detail, not the primary contract between stages.

## Internal Flow

The future steady-state flow should be:

1. `target`
   - resolve training vs inference
   - resolve framework
   - resolve environment and asset sources
2. `probe`
   - check environment
   - check required assets
   - synthesize blockers and warnings
3. `repair`
   - repair user-space environment issues
   - download missing model or dataset assets
   - materialize recipe templates
   - generate scripts only with explicit user approval
4. `report`
   - emit the final verdict and next action

`auto` should remain only as a compatibility alias for `fix`.

## Asset Rules

Default required assets by target:

- training: `script + model + dataset`
- inference: `script + model`

Optional assets such as `config` or `checkpoint` become required only when the
target actually depends on them.

The agent must not guess ambiguous asset sources. Auto-repair is valid only
when the source is deterministic.

## Artifact Policy

The default output should be minimal:

- `readiness-output/report.json`
- `readiness-output/report.md`

Intermediate JSON files should be reduced over time. The long-term direction is
to keep a single optional debug snapshot, not one persisted file per internal
stage.

During migration, compatibility shims are acceptable as long as the public
contract keeps getting simpler.

## Refactor Plan

1. Introduce explicit state and path objects so the pipeline stops passing
   loose dictionaries.
2. Collapse stage boundaries around `target`, `probe`, `repair`, and `report`.
3. Reduce intermediate artifact persistence.
4. Move recipe-specific logic out of the generic readiness path.
5. Update tests to validate the simplified contract instead of stage-by-stage
   helper plumbing.

## Step Review Rule

After each refactor step, verify these questions before continuing:

- Does the change move the skill closer to `target -> probe -> repair -> report`?
- Does it reduce implementation sprawl or at least create a cleaner seam for
  the next reduction?
- Does it preserve the hard constraints on mirrors, safe user-space repair, and
  asset handling?
- Does it avoid reintroducing generic certification complexity?
