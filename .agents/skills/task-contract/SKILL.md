---
name: task-contract
description: Scope requested implementation into this repository's contract and owned files. Use at task startup when no adequate contract exists; skip read-only questions.
---

# Task contract

Use the existing [contract template](../../../tasks/contracts/TEMPLATE.md) and [workflow](../../../docs/workflow.md). This skill supports an implementation request; a question, recommendation or code review alone does not authorize implementation or require a new contract.

First look for the assigned contract. Reuse it when it already captures the current outcome and authority. Otherwise identify a bounded task ID and capture the user's desired behavior, allowed files, acceptance criteria, verification and rollback in a new contract.

Inspect current Git status, branch, worktree and base before assigning ownership. Preserve unrelated work. Retain an Emdash-owned worktree when it is the task's selected checkout; parallel editing owners require separate worktrees. Do not switch or reset another task's checkout.

State file ownership before editing. Record the implementation owner and independent reviewer using existing repository roles. Resolve routine choices from local evidence; ask only for missing information that changes the intended outcome, scope, authority or acceptance criteria, and continue independent useful work while waiting.

Define observable success rather than activity counts. Keep testing proportional to the change while retaining required final checks. Record existing approvals accurately: an authorized implementation does not authorize commits, pushes, merges, deployments, external messages, paid APIs or permission changes.

Read only relevant [architecture](../../../docs/architecture.md), decisions and known issues. Refer to canonical instructions instead of copying them into each contract. This skill neither creates background goals nor grants tools or changes client permissions.
