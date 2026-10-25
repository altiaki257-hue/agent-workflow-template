---
name: regression-debugging
description: Diagnose a reproducible defect or failing test and design a regression check. Use for actual failures, not speculative cleanup or routine formatting.
---

# Regression debugging

Read the applicable contract and use the smallest relevant implementation, caller, failing input and test. Follow the [workflow](../../../docs/workflow.md); researchers and test designers do not execute code, and an implementation request must establish file ownership before changes.

Establish expected versus observed behavior and preserve the minimal redacted failure evidence. An authorized implementer reproduces the failure with a narrow command or fixture; if execution is unavailable, label a proposed reproduction as unverified.

Trace the failing input across the actual boundary and form a hypothesis supported by the observed output. Use a targeted observation to distinguish competing causes. Stop adding speculative edits when the evidence no longer narrows the cause; identify the missing fact or access that would resolve it.

For a behavioral fix, design a check that fails for the reported defect and passes for the intended behavior. Cover a relevant failure path or trust boundary; avoid tests that reproduce implementation details or merely match wording. Use existing fixtures and Hypothesis patterns when they add meaningful coverage. Reversible documentation or formatting changes do not need artificial tests.

Make the smallest coherent fix in owned files, rerun the narrow check, then use the required [quality checks](../../../docs/quality-tools.md). Do not weaken checks, add unrelated cleanup, retry an external mutation without a bounded reason, or change providers or permissions to force a result.

Report the demonstrated cause, fix, exact verification and residual uncertainty. Keep private inputs and credentials out of prompts, fixtures, logs and handoffs. A passing reproduction is not an independent code review.
