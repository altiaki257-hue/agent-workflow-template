# PUBLIC-002: Refresh reusable archive and agent skills

- Status: done
- Assigned role: Codex
- Branch: `chore/PUBLIC-002-workflow-refresh`
- Worktree: separate public-template publication worktree
- Base commit: `ae3821e` (existing public snapshot)
- Implementation commits: `519f8fe5c91ff76d59adfe3cc8fc53e1c0694426`; a later documentation commit records verified publication
- Reviewer: independent review pending
- Integration commit: `519f8fe5c91ff76d59adfe3cc8fc53e1c0694426`, verified on remote main and the local main checkout
- Git approval: owner explicitly requested committing the pending changes to both the main and existing public repositories; commit, push and main integration are authorized
- Updated: 2026-10-25

## Goal and ownership

Publish the reusable archive naming/type fixes and fourteen agent skills while preserving the public template's separate history and sanitized defaults. Codex owns the selected source/test/documentation counterparts, the new canonical skill packages and Claude wrappers, the provenance lock and these publication records. No private task history, credentials, machine configuration, conversation notes, original Git history or unrelated source changes are included.

## Acceptance criteria

- [x] Archive changes and fourteen skills are present with upstream licenses and matching provenance hashes.
- [x] Existing public identity, README setup, reset status/backlog and sanitized source references remain intact.
- [x] Complete quality checks and intended-change privacy checks pass.
- [x] Commit is verified on public main; review status and verification are reported accurately.

## Verification and handoff

Run `python scripts/check_quality.py --security`, verify the imported/custom/wrapper hashes in the skill lock, inspect the intended diff for private identifiers and records, and verify Git refs after publication. Record outcomes in [the handoff](../handoffs/PUBLIC-002-update-to-owner.md) and [public-copy audit](../../PUBLIC-AUDIT.md). No new cloud connection or inference is authorized.

## Risks and rollback

The reusable exporter still needs local configuration and opt-in sync setup. New skills do not authorize remote operations. Public history remains separate; revert this update rather than importing private commits or rewriting the public branch. Independent review is pending.
