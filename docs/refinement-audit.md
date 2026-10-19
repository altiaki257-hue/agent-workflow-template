# OPT-004 refinement evidence

Audit base: `debf68aa620d8abd33229ccff8f995078a0e4163`, 2026-10-19. Root owns edits; independent Codex reviewed code/tests read-only. Scope covered the answer controller, role prompts, model/account gates, telemetry sanitization, evaluation/provenance, note/archive update paths and operational instructions. No ignored data, personal vault content, credentials, other worktrees or paid inference were used.

## Findings and corrections

| Demonstrated issue | Correction and evidence |
| --- | --- |
| Consult discarded already-generated draft text after the first 8,000 characters. Prefix-only clipping could also discard conclusions/corrections. | Separate critic and delivered coverage. Preserve bounded head/tail excerpts with visible middle omissions; deliver up to 16,000 draft characters, retain the 8,000-character critic limit and 5,000-character critique limit. Decisive suffix regression proves delivery and review retain tail evidence. Additional delivered text is explicitly unreviewed. |
| Worker output was JSON-decoded and usage-validated twice. | One validated iterator exhausts the stream before accepting success or availability fallback. Existing order-dependent safety controls remain; decoding-count regression requires one decode per row. |
| Replayed identified step completions doubled steps and tokens. | Count identical IDs once; reject conflicting metadata before fallback. Legacy events without IDs remain supported, without invented deduplication. |
| Non-string MCP protocol versions could raise TypeError and interrupt the server. | Validate type before version membership. Regression runs malformed initialization followed by a successful ping. |
| Extremely large numeric metadata could raise OverflowError; fractional token counts were accepted. | Bound values before float conversion, require integer token counts, retain finite fractional costs. Malformed metadata vetoes availability fallback in either event order. |
| Blind pairs could compare explicitly incompatible evidence scopes. | Reject invalid/disagreeing case/row/result scope values. Preserve historical artifacts with absent fields without inventing provenance. |
| Catalog dictionaries could masquerade as tool-support lists; malformed account records could escape safe errors. | Validate catalog/identity/pricing/tool/expiry shapes and account record types. No model, credential or permission assignments change. |
| A prefixed recommendation to report zero passed after acknowledging unknown usage. | Add bounded affirmative-prefix controls while retaining negation/quotation controls. This remains a narrow diagnostic, not a semantic grader. |
| Repeated curated-note setup rewrote an unchanged brief. | Skip the atomic rewrite when managed text is unchanged; regression makes unnecessary writes fail. Personal annotations and conservative metadata validation remain. |
| README still claimed all checks needed no dependencies; current status repeated detailed historical results. | Correct Hypothesis setup requirements, distinguish current and historical artifact behavior, and replace status history with links to authoritative records. |

## Measurements and interpretation

On this Windows/Python 3.12 host, a synthetic 3,000-event stream with 1,000 completed steps was parsed seven times per implementation. Median baseline parsing was **49.21 ms**, refined **31.43 ms** (about 36% less local parsing time). JSON decodes fell from 6,000 to 3,000. Both produced 1,000 steps and 100,000 input tokens. This is a small local processing benchmark, not a model speed or token-usage benchmark; no hard latency guarantee follows.

Normal bounded draft/critique text remains intact. Oversized drafts can now give synthesis more useful evidence, deliberately increasing context relative to the old destructive clip. Parent delivery is still bounded and partial review remains explicit. At refinement verification, the current-status file fell from 3,868 to 2,257 Unicode characters (about 41.6% less text), reducing retrieval when that file is read; actual inference-token savings were not measured. No live answer-quality comparison was run, so regression fixes establish corrected behavior rather than a general quality ranking.

## Retained boundaries and unresolved limits

Full source/merged-policy preflight remains on every request; caching it would risk stale permissions. Distinct-model critique, required synthesis, guarded free providers, single classified availability fallback and isolated metadata-only export remain. No extra classifier, recursive team, automatic response cache, model server, new dependency or provider was introduced.

Head/tail excerpts still omit middle material. Models can miss visible facts; completed critique is not proof. Legacy missing IDs/scopes prevent reliable deduplication/provenance checks. Regex evaluation cannot interpret arbitrary language. Worker stdout is still buffered by the native-client boundary, and inherited OpenCode context/retries remain outside a hard token/latency guarantee. These were retained rather than addressed through an untested transport or host rewrite.

See the handoff (private project record omitted) for exact final checks, review and installation state. Existing [known issues](known-issues.md) retain broader operational limits.
