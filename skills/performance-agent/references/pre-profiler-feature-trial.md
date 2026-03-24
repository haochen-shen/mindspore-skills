# Pre-Profiler Feature Trial

Read this file when the user selects `Path 1: Trial Existing Performance Features`.

## Goal

Let the user try known performance features before paying the cost of profiler
collection and trace interpretation.

This path is for low-cost feature trials and end-to-end validation, not root
cause diagnosis.

## Factory Query Order

Use this access order:

1. `ms-cli factory query ...`
2. `MS_FACTORY_PATH`
3. a user-provided local `incubating/factory` path

Concrete query shapes when the CLI exists:

- `ms-cli factory query list --type perf_feature`
- `ms-cli factory query list --type model`
- `ms-cli factory query get --id <model-card-id>`

If all three are unavailable:

- say the factory feature list is unavailable
- do not invent features
- keep the profiler path available

## What to Read

Primary cards:

- `perf_feature`
- `model`

In v1, do not use `known_issue` in this path.

## Filtering

Keep only features that match the current context:

- kind is `perf_feature`
- platform matches current Ascend target
- method matches when the method is known

If model identity is known, look for a matching `model` card and prefer its
`verified_perf_features`.

Matching rule:

- match on model identity when known
- match on method when known
- match on platform when known
- if several model cards remain, prefer the most specific full match

## Ranking

Default ranking order:

1. verified features from the matching model card
2. compatible features whose category matches the current metric focus
3. the remaining compatible features

Metric-to-category preference:

- throughput: `compute`, `communication`, `compilation`
- latency: `compute`, `communication`, `compilation`
- memory: `memory`

## User-Facing Summary

For each recommended feature, show only:

- name
- category
- expected gain
- one-line summary
- whether `config_diff` or `code_diff` exists
- whether it is verified on a matching model card

Show:

- top 1 to top 3 recommended features first
- the remaining compatible list after that

## Trial Rules

When the user picks one or more features:

- keep the run comparable
- rerun the same workload
- compare only end-to-end metrics:
  - throughput
  - latency
  - step time
  - peak memory

Do not:

- claim the bottleneck is proven
- explain the result with profiler evidence
- auto-enable features the user did not choose

## Round Boundary

After every feature trial round:

- summarize the before/after change
- explicitly ask whether to move to the profiler path

The user may continue feature trials, but the profiler question must reappear
after each round.
