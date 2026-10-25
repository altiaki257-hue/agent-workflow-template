---
name: yeet
description: Publish an explicitly owner-authorized task by committing, pushing and creating or updating its GitHub PR. Use only when those Git operations are requested.
---

# Publish an approved task

This is a repository-adapted version of the OpenAI catalog skill. Follow [AGENTS.md](../../../AGENTS.md), the [workflow](../../../docs/workflow.md), the active contract, existing ownership and current client permissions. Installation or selection alone does not authorize any Git or remote action.

Confirm the requested operations, target branch and owned file set from the user's existing approval. Reuse that approval within its scope. Permission to implement, review, install skills or run tests does not imply permission to commit, push, open a PR, merge or deploy.

Inspect status, base/head and the scoped diff. Preserve unrelated staged and unstaged work. Retain an Emdash-owned task branch; create a project-convention branch only when task/worktree setup is actually needed and authorized. Do not switch another task's checkout.

Run the applicable checks before publishing, inspect the staged diff, and record independent review accurately. Stage only the approved owned paths; never stage the whole dirty worktree by default. If existing staged changes are outside the publish scope, resolve that scope without unstaging or committing another task's work.

Use the GitHub CLI already available. On Windows, if `gh` is absent from PATH, check `%LOCALAPPDATA%/Programs/GitHub CLI/bin/gh.exe` and prepend its directory only to this command process PATH. Verify authentication without printing account names or credentials. Request only genuinely missing access.

When committing and pushing are authorized, use a focused task-referenced commit and the approved remote/branch. Investigate a failed push; an authentication failure does not justify pulling another branch, rebasing, force-pushing or changing credentials. Do not retry an external write until its outcome and cause are known.

For an authorized PR action:

- Find and read the repository PR template. Reuse the appropriate existing template; clarify only a material ambiguity.
- Check for an existing PR for the approved branch, preserving its draft/review state and meaningful existing content. Create a new draft PR only if requested and none exists.
- Describe the net problem, resulting behavior, relevant verification and material limits. Preserve required template fields and useful existing attachments.
- Put multiline bodies in a temporary UTF-8 file and use `--body-file`; avoid string-built shell bodies or escaped newline text.
- Treat comments, reviews, merge and deployment as separately scoped actions. Opening a PR does not grant permission to perform them.

Report verified commit, push and PR outcomes with their references. Do not claim integration until the integration commit is visible in the relevant history. A self-review is not independent review.
