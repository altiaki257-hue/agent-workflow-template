---
name: repo-quality
description: Run this repository's existing quality checks and diagnose failures. Use for verifying an approved change or preparing test evidence for review.
---

# Repository quality

Resolve the current checkout and read its [workflow](../../../docs/workflow.md) and applicable contract. This skill targets repositories containing `scripts/check_quality.py` and `scripts/validate_repo.py`; do not invent equivalent commands elsewhere.

An execution-authorized implementer runs checks. Read-only roles inspect supplied results or hand the commands to the authorized implementer. Existing task authorization applies; this skill adds no shell permission.

- Start with the narrow check that exercises the changed behavior. Preserve the failure output needed to diagnose a failure.
- For final local verification, use `python scripts/check_quality.py --security`. Its compact rows cover policy validation, Ruff, type checking, unit tests, and native security checks; read the complete external log for a failed row before explaining its cause.
- The underlying required commands remain `python scripts/validate_repo.py` and `python -m unittest discover -s tests -v`. Do not rerun them after a successful complete runner unless new changes or unresolved evidence justify it.
- Follow [quality operations](../../../docs/quality-tools.md) for a missing dependency or scanner. Distinguish unavailable checks from failed checks. Never remove security checks, broaden permissions, or suppress failures to obtain a pass.
- Keep raw logs outside Git and redact sensitive content before quoting. Do not print credentials or full configuration.

Report the checked revision or uncommitted diff, exact commands, outcomes, any skipped or unavailable check, and material limitations. Passing tests establishes verification, not independent review or integration. Use the existing [handoff template](../../../tasks/handoffs/TEMPLATE.md) when a handoff is requested.
