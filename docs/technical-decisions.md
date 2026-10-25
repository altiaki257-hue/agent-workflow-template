# Technical decisions

## LOG-003: Stable chronological archive filenames

Owner-authorized 2026-10-20. Use UTC creation timestamps, safe readable titles and a deterministic short identity suffix. Store the assigned filename separately from the display title so incremental updates and title changes cannot create duplicates. Sort the index by normalized creation time and use wikilinks. Migrate owned legacy notes without overwriting destinations or annotations; keep cached notes when source transcripts disappear. Live migration uses Obsidian-aware renames for backlinks and matching cloud item renames. No model calls, new package or change to curated project-note naming is needed.

## LOG-002: Opt-in archive sync through the existing plugin

Owner-authorized 2026-10-20. Keep the exporter local by default. Opt-in cloud sync uses a fixed Obsidian CLI command after verifying the open vault path, so no cloud SDK or credentials enter the exporter. Dispatch failures record a deferred request and cannot invalidate archived notes. Plugin startup/periodic timers handle closed-app catch-up and transfer failures. Acknowledgement means requested, not delivered. Remotely Save 0.5.25's on-save handler checks the active note, so it cannot replace explicit dispatch for background exports. No inference or new package dependency is introduced.

## TD-020: Measure coverage and audit isolated dependency profiles

**Accepted 2026-10-19, OPT-005.** Pin coverage.py for branch measurement and pip-audit in an isolated tool environment. Keep full measurements outside Git, expose bounded summaries, and treat failed tests, incomplete audits and known vulnerabilities as failures. CI measures its existing suite once; dependency advisories run separately on a schedule/manual trigger. Audit dev/observability and auditor profiles separately. Replace Semgrep's vulnerable MCP Python environment with official native Opengrep 1.31.0, with OS/architecture-specific SHA256 pins, explicit installation and unchanged local rules/controls. Semgrep still requires an affected exact SDK version; forcing an override or downgrading the scanner was rejected. This also removes its incompatible OpenTelemetry requirement. Native release integrity is checked separately from Python advisory auditing; no claim of an exhaustive native vulnerability audit follows. Retain model assignments pending task-specific evidence; the dated [free-agent review](free-agent-review.md) distinguishes verified quotas, trials, benchmark settings and privacy. Partial-review notices are controller-enforced across all MCP routes.

## TD-019: Preserve evidence with explicit coverage

**Accepted 2026-10-19, OPT-004.** Keep critic input and synthesis delivery independently bounded; use labelled head/tail omissions and exact character coverage instead of silently throwing away generated conclusions. Partial critic coverage never certifies additional delivered text. Decode each worker event once while retaining full-stream fallback vetoes; identified completion replays cannot inflate usage. Reject malformed numeric/catalog/account metadata and explicit comparison-scope conflicts safely. Reduce duplicated current-memory history, not security checks or critique. No new model/provider, caching layer or live classifier. See [audit measurements and limits](refinement-audit.md).

## TD-018: Local quality checks and curated notes

**Accepted 2026-10-18, SETUP-002.** Extend existing Ruff correctness checks with bugbear, use one basedpyright checker without a baseline, and add generated privacy-boundary tests plus three local Semgrep security rules with controls. Keep runtime imports standard-library only and optional SDK typing in development dependencies. Compact successful check output while retaining complete failures outside Git. RTK OSS remains an explicit wrapper because this host's automatic hook compatibility is unverified; disable its tracking/network telemetry. No savings claim follows merely from installation.

Use native Obsidian CLI and core Templates/Properties/Bases with selective skills before introducing duplicate memory/services/community plugins. Keep Git authoritative and archive retrieval explicit. Preserve personal annotations and fail closed on unsupported owned metadata. Installed Emdash forwards selected effort; no automatic prompt classifier was found in the inspected path. Workflow sizing does not change that actual parameter. See [tool inventory and limits](agent-efficiency.md) and [notes](note-taking.md).

## TD-016: Isolated opt-in telemetry and terminal quota handling

Accepted 2026-10-18, OBS-001/QA-003/OPS-001. Keep the answer runtime standard-library-only. An explicit opt-in launches a separate exporter process with sanitized JSON on anonymous-file stdin and a narrow environment. Optional pinned Langfuse 5.0.2/OTEL code, network flush and child cleanup run outside answer execution; the daemon reaper requires a living controller. Missing SDK/credentials or export failure cannot replace the answer. Export fixed names, reviewed identifiers, timings and usage/coverage only; remove input/output, identities, raw errors, paths, unknown metadata and SDK scope/resource/event/link attributes. Verify actual delivered observations against the exact schema. Best-effort metadata is not complete billing or parent-usage coverage. See [observability](observability.md).

Classify only exact bounded structured terminal quota identifiers before availability fallback. Ordinary transient 429s retain the single reviewed runner-up. OpenCode 1.19.3's internal retries precede its final error event; no supported override was verified, so do not invent one or claim those delays eliminated. Keep raw provider bodies private.

## TD-017: Recoverable comparison and procedural merge checks

Accepted 2026-10-18, MEASURE-001/OPS-001. Use seeded sequential counterbalance, supplied evidence and rubric isolation for fresh synthetic comparisons. Persist completed rows incrementally outside every Git checkout, refuse overwrite, and retain failures/unknown usage. Produce actual parent syntheses separately before revealing direct answers; blind judgments to routes and telemetry. Unknown parent usage/time prevents complete combined cost/latency claims. See [observed results](answer-evaluation.md#ops-001-fresh-comparison-2026-10-18).

The approved GitHub protection check returned HTTP 403 requiring Pro or public visibility for this private repository. Preserve billing/visibility. Verify all platform, quality and aggregate checks against the exact current head before merging procedurally; report that server-enforced protection remains unavailable.

## TD-015: Evidence scope and diagnostic assertions

Accepted 2026-10-18, OPT-003. Declare benchmark scope in each case and record it with each result. Keep repository scope for missing repository facts, use tool-free supplied scope for self-contained hypothetical cases, and retain the repository default for older case files. Parent consultation uses explicit CLI `--mode consult` when MCP is unavailable, avoiding an unnecessary worker synthesis before parent synthesis.

Replace single-keyword evaluation assertions with fixed standard-library Python relationship checks and selected contrary-claim checks. JSON fixtures allow offline tests to exercise the actual ten cases and negative controls without adding a YAML dependency to the controller/test runtime. Reuse the same assertion function in Promptfoo. These bounded phrase checks require human review and can still misclassify unfamiliar phrasings; no model grader, answer cache, routing change or inference-token-saving claim is introduced.

## TD-014: Offline quality gates and opt-in model evaluations

Accepted 2026-10-18, QUALITY-001. Pin development lint/hook versions separately from the standard-library controller runtime. Use Ruff's correctness rules without automatic rewriting, actionlint's native workflow checks, staged redacted Gitleaks scans and a distinct full-available-history CI scan. Keep the existing current-file policy scanner and platform tests; the aggregate gate requires the new quality job. Gitleaks is feature complete with security maintenance, chosen initially for its established CLI/hooks; reassess Betterleaks before new scanner feature work. Hook environments bootstrap their own Go toolchain, avoiding a global Go requirement.

Promptfoo defaults to deterministic synthetic fixtures and uses no model grader. Live evaluation requires an explicit flag, is sequential and initially limited to one case, and calls the existing guarded direct/review controller with supplied evidence. Standalone review includes synthesis; provisional consult drafts cannot be graded as final. Unknown token usage and catalog-versus-billing distinctions remain in metadata. Disable telemetry/sharing/cache/database writes through the runner and store outputs outside Git. A Langfuse SDK installation or successful authentication does not establish trace delivery; external export requires an explicitly scoped implementation. See [setup, evidence limits and owner actions](quality-tools.md).

## TD-001: Git-backed memory

**Accepted 2026-10-17.** Contracts, concise docs, commits, and handoffs transfer context; chat memory is never assumed.

## TD-002: One editing agent per worktree

**Accepted 2026-10-17.** Emdash assigns each active editing task a separate branch/worktree. Read-only inspection may share a worktree; concurrent editing may not. Emdash-managed sibling worktrees are preferred over a repository-local directory.

## TD-003: Cloud-only, free-default models (original assignments superseded by TD-012)

**Accepted 2026-10-17.** The live OpenRouter catalog was checked on 2026-10-17. The following are historical assignments; TD-012 and [current routing](model-routing.md) supersede their model/provider selections. The original defaults used explicit `:free` IDs with provider fallbacks disabled:

- Coordinator/research: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`
- Independent answer critique/helper: `openrouter/thinkingmachines/inkling:free`
- Test design: `openrouter/nvidia/nemotron-3.5-lightning:free`
- Routine edits: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`

GLM-5.3-Flash (`z-ai/glm-5.3-flash`) and Gemini 3.1 Flash Lite (`google/gemini-3.1-flash-lite`) were available only as priced endpoints, so they are not configured. Re-check the catalog when an ID fails. Never remove `:free` or enable paid fallback without approval; approved total paid usage is capped at US$5/month.

OPT-001 replaced Laguna S 2.1 after catalog verification showed its scheduled 2026-10-31 expiry. QA-001 selects Super and Inkling after synthetic live responses; Ultra/Lightning checks timed out. Their definitions remain available without automatic switching. The helper explicitly uses free Inkling. These are availability choices, not a model-quality ranking. A provider allowlist, exact model whitelist, zero prompt/completion/request price caps, and disabled provider fallback provide layered cost controls. They do not enforce the aggregate approved US$5 budget across providers.

## TD-004: Policy-only baseline CI

**Accepted 2026-10-17.** With no application stack, Python standard-library tests validate workflow configuration and common secret patterns. Extend CI when application code exists.

OPT-001 adds an executable offline validator and negative regression cases; there are no third-party Python dependencies. Live model checks are separate from CI so network outages do not block unrelated changes. CI uses pinned action revisions without persisted Git credentials, with Linux/Python 3.13 and Windows/Python 3.11 coverage.

## TD-005: Explicit OpenCode role gates

**Accepted 2026-10-17.** Models and permissions live together in JSON so validation reads actual configuration, not strings in Markdown. Prompt files contain role text only. QA-001 makes the default a read-only answer coordinator with access only to the named answer-team MCP tool. Shell commands are denied for read-only roles: even a test command executes arbitrary repository code and may write files. Junior edits and all shell commands require approval. Unknown tools/MCP and native task delegation default to deny; unrestricted built-in profiles are disabled. Web requests require researcher approval and are denied inside unattended bridge workers. These are client guardrails rather than an OS sandbox.

## TD-006: Compact, shared memory

**Accepted 2026-10-17.** Claude imports AGENTS.md directly. Serena is optional retrieval-only infrastructure for the actual Python scripts/tests; canonical memory remains in docs/contracts/handoffs. Historical setup records describe verified integration, while live status points to Git instead of duplicating every HEAD hash.

## TD-007: Enforced, bounded answer review

**Accepted 2026-10-17.** QA-001 uses a local stdlib controller with free cloud inference, exposed as one read-only MCP tool to OpenCode and Codex. A prompt-only trial claimed specialist review without invoking any specialists; that result was rejected. The controller therefore enforces draft/research → distinct-model critic → synthesis and returns completion metadata only after all required worker stages succeed. Native task delegation remains denied and workers cannot invoke the bridge. Simple interactive questions avoid it. CLI `auto` includes worker synthesis without a classification call; TD-008 changes MCP `auto` to two-worker consultation followed by parent synthesis. ROUTING-001 supersedes the original no-retry rule with one classified availability runner-up; paid fallback, recursive debate and unattended external browsing remain absent. Codex and OpenCode tool timeouts accommodate a bounded three-stage run. See [operations and limits](answer-pipeline.md).

## TD-008: Parent synthesis for client consultations

**Accepted 2026-10-17.** QA-002 removes redundant free-worker synthesis from MCP auto/consult: researcher drafts, a distinct model critiques, then the existing parent Codex/OpenCode assistant synthesizes both. Consult returns separate bounded artifacts with `synthesis_required`, never an already final answer; critic failure remains an error. Standalone CLI auto/review/research retains worker synthesis. End-to-end and per-stage reported usage expose efficiency limits; small diagnostic comparisons do not establish a global quality ranking. Read-only/client cost boundaries remain unchanged, and unsafe agent/provider overrides plus enabled unknown MCP servers are rejected. See [evaluation evidence](answer-evaluation.md).

## Recommended `main` protection

If the repository becomes eligible, require pull requests, the aggregate `repository-policy` check, conversation resolution, blocked force pushes/deletion and no routine bypass. A solo owner cannot approve their own PR: use independent Codex review procedurally and set the approval count to zero until another eligible reviewer is available. With another reviewer, require one approval and dismiss stale approvals. Require linear history only if squash/rebase is adopted. GitHub cannot verify model identity. OPS-001 attempted protection with owner approval; the private-repository account plan returned HTTP 403. No billing, visibility or protection setting was changed.

## Verified source references

- [OpenCode configuration](https://opencode.ai/docs/config/) and [agent permissions](https://opencode.ai/docs/agents/): v1 fields used by installed OpenCode 1.19.3.
- [OpenRouter catalog](https://openrouter.ai/api/v1/models) and [price routing](https://openrouter.ai/docs/guides/routing/provider-selection#max-price): exact free IDs and request price caps.
- [Claude memory imports](https://code.claude.com/docs/en/memory#import-additional-files): direct shared-rule import.

## TD-011: Manual account-tier pilots (superseded by TD-012 for automatic routing)

**Accepted 2026-10-17, MODELS-001.** Google/Groq free-account allowances are not zero-priced model variants. Add only exact reviewed built-in model allowlists, with no URL/SDK/cost/request overrides. Keep all default/helper/automatic agent roles pinned to existing OpenRouter free endpoints. Do not weaken zero-price catalog validation or treat positive SDK cost estimates as proof of billed charges or zero cost. A separate read-only authentication/model-list diagnostic is honest about its limits. Direct inference requires confirmed free account tiers or separate paid approval; automatic cross-provider fallback remains absent. This supports controlled evaluation without pretending that a local config can certify cloud billing state.

## TD-012: Role-specific free defaults and bounded runner-ups

**Accepted 2026-10-17, ROUTING-001.** The owner requested automatic assignments and runner-ups after explicitly confirming free tiers with paid billing disabled. Use exact reviewed built-in direct models without price/endpoint aliases. ROLE_MODELS drives strict role validation and bridge candidate order; primary config and explicit backup commands must match. One configured runner-up is allowed only after structured transient HTTP failures within the existing deadline. Policy/auth/unknown/timeout failures stop. Exclude the actual successful draft model from critique, or fail rather than claiming independence. Bind direct bridge inference to a fresh local owner confirmation and exact credential fingerprint; interactive OpenCode bypasses that controller guard and depends on provider billing controls. SDK dollar estimates remain labelled catalog metadata, not billed cost or proof of free usage. Small synthetic probes guide provisional choices; they do not establish a global ranking. See [selection evidence and limits](model-routing.md).

## TD-013: Selected-endpoint checks and single-copy MCP answers

**Accepted 2026-10-17, CONTROLLER-001.** Preserve complete local/merged policy validation on every request. Fetch/check public pricing, tools and expiry only for an OpenRouter candidate about to run, using the existing public catalog cache. Bind worker main/helper/agent model selection to that exact reviewed candidate, so direct workers do not depend on OpenRouter. Keep the separate full catalog diagnostic unchanged. Divide the remaining request budget across required stages; unused time carries forward, while each fallback shares its stage budget. Socket inactivity timeouts and process cleanup do not guarantee a hard elapsed SLA. Preserve unknown telemetry explicitly with per-field coverage; missing values cannot count as observed zero. MCP bridge 2.0.0 retains prose once in text plus structured provenance/metrics with an answer-location pointer. CLI JSON remains unchanged apart from richer usage metadata. The transport version announces the structured-prose field removal; legacy text clients retain answers and safety notices. See [operations and migration](answer-pipeline.md).


## OPT-002: Explicit evidence scope and reliable completion

Accepted 2026-10-17. Preserve default repository retrieval and the small architecture excerpt that previously corrected project-identity errors. Let callers explicitly choose supplied evidence when all case facts are present; deny worker tools and omit injected identity in that mode while retaining full safety preflight, independent critique and parent synthesis. Do not guess scope or retry a missing-evidence case automatically. Native OpenCode 1.19.3 debug-agent checks confirm deny-all overrides for researcher, critic and coordinator; reject any observed tool use as an additional fail-closed check.

Associate completion with the returned message when provider IDs exist, invalidate prior text after a new step/tool, and reject malformed event metadata before availability fallback. Tell the critic about draft truncation. Consolidate duplicate coordinator routes and keep current status brief, preserving historical handoffs. No new dependency, response cache, model reassignment or telemetry removal is introduced. Report character reductions separately from measured inference-token or answer-quality improvements.
