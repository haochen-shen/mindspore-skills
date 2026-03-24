# Performance Agent Optimization Plan

This document records the recommended next steps for improving
`performance-agent` after the current automation chain:

- `collect_msprof.sh`
- `summarize_msprof_hotspots.py`
- `build_hotspot_brief.py`

Current focus is answer quality and operational stability for Ascend/NPU
performance analysis across MindSpore and `torch_npu`.

## Current State

The skill now supports two main runtime paths:

1. trial existing performance features from the `ms-cli` factory knowledge
   base
2. run profiler-led bottleneck diagnosis and validation

The profiler path still supports a practical flow:

1. identify the real Python training entry script
2. copy it to a `*-perf.py` sibling
3. inject the official MindSpore or `torch_npu` profiler hooks into the copy
   only when the copied script matches a supported explicit-loop template
4. otherwise guide the user to modify the copied script manually
5. rerun the workload with the copied script
6. collect profiling artifacts
7. summarize operator hotspots
8. build a compact hotspot brief
9. let the skill prioritize top hotspots and suggest optimization directions

This direction is safer than mutating the original script, but it still depends
on environment-specific script structure and synthetic smoke tests more than
real profiling samples.

The older idea of wrapping the original command in a universal external
`msprof` launcher should not be treated as the baseline design.

The newer top-level design change is:

- keep `Path 1` and `Path 2` explicit instead of hiding feature trials inside a
  profiler-only flow
- let users choose between low-cost feature trials and profiler evidence
  collection
- keep Path 1 output light and end-to-end metric focused
- keep Path 2 output evidence-heavy and trace-driven

## Decision Log

Current collection-automation decisions:

- automatic profiler injection is supported only for explicit training-loop
  templates
- supported templates are:
  - MindSpore explicit training loop
  - `torch_npu` explicit training loop
- if the copied script does not match one of those templates cleanly, the skill
  must not guess where to inject profiler code
- in unsupported or ambiguous cases, the skill should guide the user to modify
  the copied `*-perf.py` script manually for profiler collection
- MindSpore `model.train(...)` style entries are currently treated as
  unsupported for automatic injection unless a project-proven safe pattern is
  introduced later

Current path-structure decisions:

- the skill now has two explicit top-level paths:
  - trial existing performance features
  - profile and diagnose bottlenecks
- if the user intent is explicit, the skill may enter the requested path
  directly
- if the user intent is ambiguous, the skill should present the two path
  choices and ask the user to pick one
- if the user chooses Path 1 and runs a feature trial, the skill must ask after
  each round whether to switch to Path 2
- Path 1 must not claim a bottleneck is proven from end-to-end trial data alone
- Path 2 keeps the existing profiler-led dominant-bottleneck workflow

Current factory-integration decisions for Path 1:

- prefer `ms-cli factory query ...` when available
- otherwise fall back to `MS_FACTORY_PATH`
- otherwise fall back to an explicitly provided local `incubating/factory`
  path
- Path 1 currently uses:
  - `perf_feature`
  - `model`
- Path 1 currently does not use `known_issue` in the default workflow
- matching model cards should prefer model + method + platform specificity
- top recommendations should prioritize `model.verified_perf_features` before
  generic compatible features

## Archived Detail from `SKILL.md`

The top-level `SKILL.md` was intentionally thinned into a runtime control
surface. The following detail was removed from the main file and is preserved
here as optimization context rather than runtime instruction:

- the longer narrative framing around profiler-first diagnosis
- the expanded step-by-step explanation of collection, classification,
  optimization, and rerun stages
- helper-path design notes that describe future collection automation beyond the
  currently safe capability gates
- verbose examples and motivational explanation that improve human readability
  but add noise to the AI control surface

The intent of the split is:

- `SKILL.md` stays short, state-driven, and safe for immediate execution
- `references/` holds on-demand operational detail
- this file holds roadmap, design rationale, deferred ideas, and archived
  detail that should not steer runtime behavior unless deliberately promoted
  later

If any removed detail needs to become active behavior again, it should be
reintroduced only after it is rewritten as a current, testable capability
rather than as descriptive narrative.

## Priority Roadmap

### 1. Use Real `msprof` Samples to Improve Answer Quality

Collect 3 to 5 real Ascend profiling outputs and use them to evaluate the
quality of `performance-agent` responses.

Recommended coverage:

- communication-dominant case
- host gap or launch-overhead case
- graph compile or recompilation case
- memory-heavy operator case
- optimizer or update dominant case

For each sample, check whether the skill:

- starts from the highest-cost hotspot
- classifies the bottleneck correctly
- gives one focused first optimization
- ties rerun metrics to the chosen bottleneck
- avoids broad generic optimization lists

### 2. Add an `msprof` Layout Reference

Current scripts detect operator tables heuristically by scanning CSV or TXT
files and matching generic column names.

Add a reference document under `skills/performance-agent/references/` that
describes the `msprof` layouts commonly seen in your environment:

- common export directory structure
- common file names
- common column names for operator, time, memory, stage, and communication
- which files are most reliable for hotspot ranking

This will let the scripts become more deterministic and reduce guesswork.

Status:

- a runtime layout reference now exists to help the skill interpret profiler
  exports and request the smallest high-signal files first
- follow-up work is still needed if you want scripts to use the layout more
  deterministically instead of heuristic scanning only

### 3. Expand Script Outputs Beyond Operator Hotspots

Current automation is operator-centric. That is a good starting point, but it
does not cover all major bottleneck families cleanly.

Recommended next script outputs:

- communication hotspot summary
- memory hotspot summary
- stage breakdown summary
- compile or graph-build summary

These can be emitted as small JSON files so the skill can reason from a stable
input layer instead of parsing raw `msprof` artifacts repeatedly.

### 4. Strengthen Mapping from Hotspot to First Optimization Direction

Right now the scripts distinguish only broad categories such as
`communication` and `computation_or_other`.

Add a more explicit mapping layer, for example:

- `AllReduce`, `ReduceScatter`, `AllGather` -> overlap, fusion, bucketization
- `MatMul`, `BatchMatMul` -> fusion, shape/path checks, kernel-path review
- `Cast` -> dtype-path cleanup, redundant cast removal
- memory-heavy activation ops -> recomputation or checkpointing review

This can be stored in a small reference file or machine-readable mapping table.

The goal is to make the first suggested optimization direction more consistent
across runs.

### 5. Add Quality-Focused Evals

Do not focus only on trigger behavior.

Add evals that measure whether the skill:

- prioritizes top 1 to top 3 hotspots
- explains why top 1 is first
- avoids spreading effort across the long tail
- ties evidence to the selected optimization
- chooses rerun metrics that actually match the bottleneck

These evals should be built around realistic `msprof` sample summaries rather
than abstract prompts only.

The latest skill update also needs eval coverage for the new path split:

- whether the skill keeps Path 1 and Path 2 distinct
- whether explicit user intent can route directly into one path
- whether ambiguous requests cause the skill to surface both paths
- whether Path 1 stays lightweight and does not drift into fake bottleneck
  claims
- whether Path 1 asks after each round whether to move into Path 2
- whether Path 2 still preserves the existing profiler-first discipline once
  selected

### 6. Improve Controlled Collection Only After Analysis Stabilizes

The current helper path should remain intentionally scaffolded, not fully
controlled.

Do not rush into a fully controlled execution workflow until:

- `collect_msprof.sh` is stable in the target environment
- result layout is well understood
- hotspot summaries are reliable
- answer quality on real trace samples is acceptable

Only after that should you consider:

- stronger automation in `collect_msprof.sh` for `*-perf.py` generation and
  minimal profiler injection
- post-run extraction of more structured summaries
- moving the skill from manual-first toward a controlled workflow

## Suggested Immediate Next Work

If work resumes later, the best next tasks are:

1. build quality evals for the new two-path structure
2. collect 3 to 5 real profiling samples for Path 2 answer-quality checks
3. tighten factory query integration so Path 1 uses a stable command or API
   surface instead of prompt-level guesswork
4. define whether and how `known_issue` should eventually participate in Path 1
   filtering

These tasks improve runtime stability without prematurely expanding automation
in the profiler collection helpers.

## Notes

- Keep comments, script output, and generated summaries in English.
- Keep the scope limited to Ascend/NPU, MindSpore, and `torch_npu`.
- Prefer real profiling evidence over expanding generic optimization advice.
