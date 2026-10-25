# Architecture

## Current state

This repository contains reusable workflow infrastructure, not application code. `opencode.json` is the source for active agent models, exact provider allowlists and permissions; `scripts/validate_repo.py::ROLE_MODELS` defines reviewed primary/runner-up pairs; `.opencode/prompts/` contains role prompts. No product runtime, database, deployment target, or public API has been selected.

## Workflow architecture

1. A backlog item becomes a contract with scope, ownership, acceptance criteria, and allowed files.
2. Emdash creates/selects a dedicated branch and worktree.
3. Claude implements complex work; free OpenCode specialists perform bounded support.
4. The implementer records tests and context in a handoff.
5. Codex independently reviews the diff against the contract and architecture.
6. A human approves any commit, push, merge, deployment, paid inference, or remote setting change.

Worktrees share Git objects but have separate working directories and indexes. Each editing agent therefore needs a distinct worktree and branch. Contracts declare file ownership to reduce merge conflicts.

## Future application architecture

When product code arrives, document verified entry points, components, data flows, trust boundaries, services, persistence, and test layers here. Do not invent architecture before requirements and code exist.

## Targeted retrieval

Prefer `rg --files`, `rg <term>`, language-server symbols, and Serena MCP. `.serena/project.yml` is portable; its cache and machine-local override are ignored.

The Serena project configuration indexes `scripts/` and `tests/` with Python support and disables edits. SERENA-001 pins standard read-only tools and the `no-memories` mode: Git-backed docs/contracts/handoffs replace Serena memory/onboarding, and unused editing/interactive mode instructions are omitted. User-global editing/interactive modes were moved from mandatory base modes to fallback defaults so this project can override them; the fallback still selects those same modes. Targeted overviews/references precede bodies; symbol-information budget remains inherited. All installed Serena 2.0 loader fields stay explicit to avoid automatic template expansion. Reconnect the client to refresh its cached configuration after edits. Register Serena in each trusted client separately; local Codex registration does not connect OpenCode workers automatically. OpenCode blocks unknown tools by default.

## Validation boundaries

- `scripts/validate_repo.py`: offline config/permission policy, tracked and non-ignored file scanning, text/Python syntax lint, and local Markdown links.
- `tests/`: regression cases for policy, secrets, Git ignore behavior, and catalog failures.
- `scripts/check_models.py`: public catalog GET, checking pricing, tool support, and expiry. It never sends prompts or credentials.
- CI: offline checks on two OS/Python combinations. Actual inference and external availability remain outside CI.

QUALITY-001 adds pinned Ruff correctness lint, actionlint workflow checks and a dedicated redacted Gitleaks history scan in a separate CI quality job required by the aggregate gate. Pre-commit runs staged secret checks and existing current-file policy validation locally. Development dependencies do not change the standard-library runtime. Optional Promptfoo evaluation defaults to synthetic fixture outputs; an explicit live runner reuses the guarded controller's direct or fully synthesized review route with supplied evidence. Evaluation results remain outside Git. See [tooling setup and boundaries](quality-tools.md).

OPT-003 declares evidence scope per benchmark case and records it with each route result. The hypothetical cases use supplied evidence without worker tools or the controller's project-memory excerpt. Promptfoo uses `scripts/evaluation_assertions.py` for deterministic relationship and selected contrary-claim checks against `evals/cases.json`; standard-library tests exercise those same assertions on correct and unsafe control answers. These checks remain bounded diagnostics, not a semantic grader or evidence of model-quality gains.

MEASURE-001 adds seeded sequential counterbalancing, source hashes and fsynced external recovery logs. Separate parent-final artifacts link to completed consult rows; `scripts/blind_answer_pairs.py` produces source-free judge packets and a separate private source/telemetry key. Missing or failed candidates stay unpaired; parent usage is never invented.

OBS-001/OPS-001 add optional metadata-only reporting in `scripts/answer_telemetry.py`. The controller sanitizes and asynchronously launches an isolated child; only that child imports the optional SDK and contacts the configured destination. Private tracing, export filtering and final instrumentation-scope scrubbing prevent content or credentials entering stored metadata. Trace failures do not block answers. See [observability operations and limits](observability.md).

OPT-004 validates worker events in one decoding pass, deduplicates identified completion replays and rejects conflicts. Bounded head/tail artifacts preserve conclusions while `artifact_coverage` separates critic input from parent delivery. Numeric and explicit comparison-scope validation fail safely. No response cache, model reassignment or permission relaxation is introduced. See the [audit evidence](refinement-audit.md).

The scanner reports paths and secret types only. It does not inspect Git history or replace a dedicated scanner. Permissions cannot contain an approved shell process or higher-precedence client overrides; see [known issues](known-issues.md).

OPT-005 adds external branch/dependency reports via `scripts/quality_metrics.py`; coverage wraps the existing CI test run, while dependency auditing is a separate scheduled/manual network check. The vulnerable Python Semgrep environment is removed; `scripts/security_scan.py` installs checksum-pinned native Opengrep outside Git and runs the same local security rules. Scans verify integrity, disable update checks and fail on findings/errors. Native scanner binaries are outside pip-audit coverage. See [quality operations](quality-tools.md) and the [dated free-agent review](free-agent-review.md).

## Optional conversation archive

LOG-003 replaces UUID filenames with stable manifest-mapped UTC creation time/title/short-identity names. Creation time drives index ordering. Owned legacy files migrate without replacing annotations or occupied destinations; source-unavailable notes remain available. The live rename callback uses Obsidian's file manager to update backlinks, while ordinary export keeps its standard-library runtime. See [archive naming and migration](chat-archive.md).

SETUP-002 adds [curated project notes](note-taking.md) beside the archive. Core Obsidian templates/properties/Bases and a narrowly triggered skill provide human navigation; Git remains canonical. `scripts/configure_notes.py` modifies explicit owned paths/settings, preserves annotations, and rejects unsupported metadata instead of guessing. [Effort and tooling evidence](agent-efficiency.md) distinguishes actual host parameters from task-sized workflow choices. No additional automatic memory service or inference router is installed.

`scripts/export_codex_chats.py` converts supported local Codex JSONL to user/assistant Markdown and reads only Emdash conversation labels/links using read-only SQLite connections. It stores generated sections in a separate Obsidian vault and preserves user annotations outside them. Incremental state, installation configuration, and status remain in the user's application-data directory. `scripts/install_chat_export.ps1` installs a standalone copy and a hidden per-user periodic task (or Startup watcher when task registration is unavailable). This archive does not feed full transcripts back into project memory or make model requests. LOG-002 adds opt-in Remotely Save dispatch after changed export batches: a fixed, bounded CLI command verifies the open vault path before requesting sync, and deferred requests retry without blocking archive success. Cloud credentials and transfer stay in the existing plugin; its periodic/startup timers handle reopening Obsidian. Default export remains local. See [operations and coverage](chat-archive.md).

## Read-only answering pipeline

`scripts/answer_team.py` is a standard-library CLI/MCP controller. OpenCode's interactive coordinator calls its `ask_team` tool; a standalone installed copy exposes the same tool to Codex. After checking full source and merged configuration, it starts native OpenCode workers with question/context on stdin. MCP auto/consult runs researcher/provisional draft → distinct-model critique, returning both for parent synthesis; standalone review/research retains worker synthesis. Simple questions and answers already supported by sufficient evidence bypass the team. Completion events establish provenance; reported usage and total/preflight/per-stage times support diagnostics. The [opt-in benchmark](answer-evaluation.md) uses synthetic versioned cases and keeps raw output outside Git.

Each worker has read/search access, bounded steps/time, no native delegation, and the bridge disabled to prevent recursion. No worker edits or launches commands. The controller can start only fixed OpenCode profiles and stop its own timed-out processes; it provides no arbitrary command tool. Agent-specific provider overrides and unknown enabled MCP servers fail policy validation before inference. Inference uses approved free OpenRouter endpoints or owner-confirmed free Google/Groq accounts. CONTROLLER-001 verifies the public catalog only for the actual OpenRouter candidate immediately before its invocation; direct workers bind both main/helper selections to their checked direct model. Each stage shares the remaining deadline fairly with required downstream stages. Per-field telemetry coverage distinguishes unknown counts from observed zero. MCP 2.x returns prose once in text and keeps provenance/usage in structured metadata; CLI JSON retains its prior answer artifacts. OPT-002 adds explicit supplied-evidence scope: omit controller project memory, deny all selected-worker tools and reject tool-use events, retaining default repository scope and required review. Completion is tied to message identity where available, and new unfinished steps invalidate older answers. `scripts/model_routing.py` enforces fresh key-bound confirmation for direct bridge calls; one configured availability fallback is permitted, retaining distinct actual draft/critic models. External browsing is denied in unattended calls. User overrides and search/symlink access remain client trust boundaries; parent UI permissions remain separate. Details, activation, and limits are in the [answer pipeline guide](answer-pipeline.md).

## Optional documentation and browser tools

Context7 CLI/find-docs is installed in the owner's user-level Claude/Codex skill and rule locations; authentication stays outside Git. It retrieves library documentation on demand and does not grant unattended OpenCode workers external access. Project Playwright instructions live in `.claude/skills/playwright-cli/`, with a small Codex discovery wrapper in `.agents/skills/playwright-cli/`. Commands retain normal approval rules; each task uses its own named, in-memory browser session. `.playwright-cli/` artifacts are ignored. Browser access is separate from model inference and from Emdash's saved Linear issue-tracker connection. The owner confirmed a successful From Issue lookup. OPS-001 verified one isolated issue write/read-back through the connected plugin; automatic tracker write-back remains off and was not tested.

## Direct hosted providers

MODELS-001 verified Groq GPT-OSS 120B/Qwen 3.8 27B and Google Gemini 3.1 Flash-Lite. ROUTING-001 promotes exact models into role-specific defaults and reviewed runner-ups. Native OpenCode backup commands preserve permissions; only the bridge implements automatic availability failover. Account confirmation lives outside Git; SDK catalog estimates are separate from billing evidence. See [routing](model-routing.md) and [provider terms](direct-provider-pilots.md).
