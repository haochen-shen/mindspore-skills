# Performance Agent Optimization Plan

This document records the recommended next steps for improving
`performance-agent` after the current automation chain:

- `collect_msprof.sh`
- `summarize_msprof_hotspots.py`
- `build_hotspot_brief.py`

Current focus is answer quality and operational stability for Ascend/NPU
performance analysis across MindSpore and `torch_npu`.

## Current State

The skill now supports a practical flow:

1. rerun the same Ascend workload under `msprof`
2. collect profiling artifacts
3. summarize operator hotspots
4. build a compact hotspot brief
5. let the skill prioritize top hotspots and suggest optimization directions

This is already useful, but it still depends on heuristics and synthetic smoke
tests more than real profiling samples.

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

### 6. Improve Controlled Collection Only After Analysis Stabilizes

The current helper path is intentionally scaffolded, not fully controlled.

Do not rush into a fully controlled execution workflow until:

- `collect_msprof.sh` is stable in the target environment
- result layout is well understood
- hotspot summaries are reliable
- answer quality on real trace samples is acceptable

Only after that should you consider:

- stronger automation in `collect_msprof.sh`
- post-run extraction of more structured summaries
- moving the skill from manual-first toward a controlled workflow

## Suggested Immediate Next Work

If work resumes later, the best first two tasks are:

1. add an `msprof` result layout reference file
2. build 3 to 5 quality eval cases from real profiling samples

These two tasks will improve both the scripts and the skill outputs without
prematurely locking in unstable automation.

## Notes

- Keep comments, script output, and generated summaries in English.
- Keep the scope limited to Ascend/NPU, MindSpore, and `torch_npu`.
- Prefer real profiling evidence over expanding generic optimization advice.
