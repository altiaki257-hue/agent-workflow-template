---
name: task-handoff
description: Prepare a repository handoff from verified Git state, contract scope and test evidence. Use when transferring work or preparing a change for review.
---

# Task handoff

Use the existing [handoff template](../../../tasks/handoffs/TEMPLATE.md) and [workflow](../../../docs/workflow.md). Resolve the task's contract and current checkout; do not create a handoff for an ordinary chat answer.

Inspect branch, worktree, base and head, the owned diff, and relevant test records. Separate this task's files from unrelated uncommitted work. Read only the relevant contract, architecture sections and previous handoff needed to resolve a fact.

Fill the template with:

- Concrete completed behavior and changed owned paths.
- Exact verification commands, observed results, and checks not run. Obtain missing execution evidence from the authorized implementer; do not turn a read-only handoff role into a test runner.
- Remaining work, decisions, material risks, rollback notes and the next required action.
- `uncommitted` until an approved commit exists, the actual reviewer and reviewed diff or commit, and a separately verified integration commit if any.

Use `review-ready`, `independently reviewed`, and `integrated` only when their evidence exists. A model's assertion is not proof that another agent reviewed the change. Reuse existing approval within its scope and record only authority still missing.

Write only the agreed handoff or task records. Keep Git canonical; use [note-taking guidance](../../../docs/note-taking.md) only when project-note maintenance is requested. Do not copy chat archives, private logs, personal data, or credentials into the handoff. Finish with the result, evidence, limitations and handoff path.
