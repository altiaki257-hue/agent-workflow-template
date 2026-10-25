---
name: evaluation-analysis
description: Assess this repository's answer-quality, usage and timing evaluations. Use for interpreting benchmark evidence or planning a bounded comparison, not ordinary answers.
---

# Evaluation analysis

Use [evaluation evidence](../../../docs/answer-evaluation.md), the applicable measurement contract, and [pipeline measurement limits](../../../docs/answer-pipeline.md#measurements-and-maintenance). Start with existing aggregate results and provenance; do not load conversation archives or private raw answers as routine context.

Check which sources, revisions, fixtures, routes, environments and attempts were measured. Distinguish draft, critique, worker synthesis and parent-final answers. Compare matching cases and identify failed or missing pairs before summarizing a difference. Use available paired and blinded evaluation artifacts rather than mixing unrelated runs.

Separate observed timings, reported token counts, cache counts and cost metadata. Missing telemetry is unknown, not zero; successful-attempt totals do not include unknown failed-attempt or parent usage. Label catalog estimates as estimates rather than billed cost. Smaller output or a shorter tool transcript does not establish better answer quality or lower end-to-end model usage.

State sample size, coverage, measured interval and material limitations. Keep small diagnostics scoped to their actual cases; do not present them as a general model ranking. Tie a quality judgment to the reviewed answer and rubric, not the model's assertion that it was reviewed.

A request to analyze existing results does not authorize new live inference. For a requested new experiment, define the comparison and success criteria first; preserve existing free-provider checks, permissions and supplied-evidence boundaries. Have the authorized role execute the applicable existing evaluator. Do not change models, enable paid fallbacks, export sensitive artifacts or add a new benchmark service implicitly.

Report the supported result, evidence and uncertainty. Record an actual improvement only when comparable measurements support it; otherwise recommend the smallest missing observation that could settle the question.
