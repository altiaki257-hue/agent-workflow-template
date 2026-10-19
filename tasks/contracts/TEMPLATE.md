# <TASK-ID>: <title>

- Status: proposed | accepted | active | review | done | blocked
- Assigned role: owner | Claude Code | Codex | researcher | test designer | junior developer
- Branch: `<type>/<task-id>-<slug>`
- Worktree: `<path>`
- Base commit: `<full-sha>`
- Implementation commits: `uncommitted`
- Reviewer: Codex
- Review target: `<commit or uncommitted diff/base>`
- Review findings/result: pending
- Integration commit: not integrated
- Git/paid-inference approvals: `<explicit scope and source, or none>`
- Updated: YYYY-MM-DD

## Goal

One concrete outcome.

## Scope

- Included files/components:
- Exclusive edit ownership (one worktree/owner):
- Supporting read-only roles:
- Excluded files/components:
- Allowed external services:
- Budget: free cloud inference by default; paid use requires approval and aggregate cap <= US$5/month

## Acceptance criteria

- [ ] Observable result.
- [ ] Security/privacy requirement.
- [ ] Documentation current.
- [ ] Relevant tests pass.
- [ ] Independent review complete.

## Verification

| Command/check | Expected | Actual |
| --- | --- | --- |
| `<command>` | `<result>` | Not run |

Baseline: `python scripts/validate_repo.py`, `python -m unittest discover -s tests -v`, and task-specific checks. Run public model preflight for OpenCode/model work; never report tests as passed when merely planned.

## Risks and rollback

- Risks:
- Recovery:

## Handoff

- File: `tasks/handoffs/<task-id>-<from>-to-<to>.md`
- Open questions/blockers:
