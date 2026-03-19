# Trace Intake Guide

Read this file when the user already has Ascend profiler output, a timeline,
memory report, or an exported trace directory.

## Goal

Ask for the smallest high-signal artifact set that allows bottleneck
classification.

## Minimum Inputs by Situation

### If the user says "I have a trace"

Ask for:

- trace directory or export path
- stack: `ms` or `pta`
- platform: Ascend/NPU
- whether the run is training or inference
- whether the run is single-card or distributed

If the user cannot share the full trace, ask for:

- top time-consuming operators
- top memory-consuming operators
- timeline screenshot or summary
- step breakdown or stage breakdown
- communication summary for distributed runs

### If the user says "I need to collect profiling data"

On Ascend/NPU, default to `msprof` as the collection path.

Ask for:

- stack: `ms` or `pta`
- whether the user needs training, inference, memory, or communication data
- the `msprof` export directory or the smallest summary view after collection

### If the user says "memory is too high"

Ask for:

- top memory-consuming operators or stages
- peak memory view or memory timeline
- batch size and precision mode

### If the user says "distributed is slow"

Ask for:

- communication-related slices in the timeline
- collective operator summaries
- whether the slowdown concentrates in backward, update, or step tail

### If the user says "inference latency is high"

Ask for:

- one representative latency trace
- graph build or compile time if shown
- host-side gap or CPU launch information if shown

## Do Not Ask For Everything

Do not request a giant checklist if the trace already contains enough evidence.
Start with what the user already has and only request missing artifacts that
block classification.

## Default Trace Reading Order

1. step or stage breakdown
2. top time-consuming operators
3. top memory-consuming operators
4. timeline gaps, synchronization, and communication slices
5. compile or graph-build sections

## Weak vs Strong Evidence

Strong evidence:

- operator tables
- timeline slices
- memory peak views
- communication summaries

Weak evidence:

- rough utilization percentages with no trace context
- high-level timing logs without trace views

If only weak evidence exists, say so explicitly and ask for the next smallest
`msprof` artifact.
