# Shared agent instructions

These rules apply to Claude Code, Codex, OpenCode, Emdash-managed agents, and humans.

## Sources of truth and roles

- Git history, task contracts, and handoffs are persistent memory. Never assume shared chat memory.
- Claude Code implements complex features and refactors. Codex owns architecture and independent review. Free OpenCode specialists handle research, documentation, test design, and routine tests.
- Emdash coordinates parallel tasks. Every editing agent uses a separate feature branch and worktree.
- Never commit, push, merge, deploy, change remote settings, or use paid inference without explicit owner approval. Reuse approval within its stated scope; do not ask again for an authorized action. New unrelated work needs its own authorization. Approved paid API use must remain at or below US$5/month across providers.

## Read selectively

Scale investigation and context to task uncertainty and consequence. Simple evidenced answers need no extra classifier or team call. This adapts workflow effort; actual model reasoning effort is a host setting, with verified limits in `docs/agent-efficiency.md`. For note maintenance, use the curated folder and source links described in `docs/note-taking.md`; do not inject conversation archives into routine tasks.

1. Use these instructions once per context; do not reread unchanged material already supplied. For implementation, read the assigned `tasks/contracts/` file. Read-only questions need no contract.
2. Read the relevant part of `docs/architecture.md` when implementation affects a boundary or the answer needs architectural facts.
3. Read decisions, known issues, and the latest relevant handoff only when applicable.
4. Use `rg`, file lists, symbols, or Serena MCP before opening broad trees. Scan the whole repository only when targeted retrieval cannot answer the question.
5. Generated files, dependencies, caches, secrets, and unrelated worktrees are out of scope.

Use [docs/workflow.md](docs/workflow.md) for startup and verification. Return concise findings with paths rather than whole-file quotations.

## Coding and architecture

- Preserve existing behavior and settings unless the contract changes them.
- Make the smallest coherent change satisfying acceptance criteria. Follow existing patterns once application code exists.
- Document new subsystems and boundaries in `docs/architecture.md`; justify dependencies and durable choices in `docs/technical-decisions.md`.
- Do not mix unrelated cleanup into a task or edit another agent's worktree.

## Security and privacy

- Never add secrets, tokens, private keys, credentials, production data, or personal data to Git, prompts, logs, task files, or handoffs.
- Use environment variables and ignored local files. Commit only redacted examples such as `.env.example`.
- While auditing, report only path, secret type, and remediation; never print values.
- Validate untrusted input at trust boundaries, use least privilege, and avoid unsafe shell interpolation or dynamic execution.
- Do not send sensitive code or data to an unapproved provider. No Ollama or local model server. OpenRouter paid fallbacks stay disabled.
- OpenCode starts in the read-only answer-coordinator role. Only it may invoke the answer-team bridge, which enforces named read-only stages; native task delegation and worker bridge access are denied. Researchers/test designers cannot execute code; an approved implementer runs tests. Junior edits and every shell command require approval. Never use `--auto`, skip-permission modes, or broad persistent approvals.
- Tool permissions are guardrails, not an OS sandbox. Ignored files must remain out of searches and prompts; inspect effective user/MCP configuration before attaching tools.

## Tests and review

- Add meaningful tests for changed behavior, failure paths, and security boundaries. Do not mirror implementation details.
- Run narrow checks first, then `python scripts/validate_repo.py` and `python -m unittest discover -s tests -v`. Record exact commands/results in the handoff. Run `python scripts/check_models.py` before new OpenCode sessions or after model changes; it performs only a public catalog GET.
- Never weaken checks to pass. Codex review must be independent and cover correctness, regressions, security, tests, and contract compliance.
- Completion requires passing acceptance criteria, current docs, and recorded unresolved risks.

## Git and handoff

- Branches: `feature/<task-id>-<slug>`, `fix/...`, `docs/...`, or `chore/...`; retain Emdash-generated `emdash/*` names when Emdash owns the worktree.
- One contract maps to one branch, one worktree, and one implementation owner. State file ownership before coding.
- Keep proposed commits focused and task-referenced, but wait for owner approval before committing.
- Before handoff, update status, test evidence, changed files, risks, and commit reference (`uncommitted` until approved).
- Use `tasks/handoffs/TEMPLATE.md`. Receivers verify Git status and rerun relevant checks.
- Never claim integration until the commit is visible in current history.
- Distinguish review-ready, independently reviewed, and integrated. Record the reviewed commit/diff, reviewer, findings, and integration commit separately.

## Memory maintenance

Keep `docs/project-status.md` factual and brief. Record durable choices in technical decisions, active defects in known issues, and queued work in the backlog. Replace stale information; do not store chat transcripts or speculation.

## Collaborative chat answers

Answer simple questions and those already supported by sufficient evidence directly. For material unresolved assumptions, consequential recommendations, uncertain repository facts, or explicit team requests, consult the `answer_team` MCP tool when available; if unavailable use `python scripts/answer_team.py --mode consult` with the question on stdin. MCP `auto`/`consult` and CLI `--mode consult` return a draft and distinct-model critique for your own synthesis. Never present the provisional draft as final. Standalone CLI `auto`/`research` retains worker synthesis for callers needing a complete answer. Consult once per question; repeat only for new evidence or changed scope. Send bounded relevant evidence, never full chats or secrets. Select `evidence_scope: supplied` (CLI `--evidence-scope supplied`) for self-contained/hypothetical cases, `repository` for missing repository facts. Cite useful evidence and disclose failure or truncation. Retain responsibility for accuracy; a critique is not factual proof. Do not turn questions into implementation tasks without user direction.
