# Operating the foundation

## Start a task

1. Pick a bounded backlog item and agree on the goal and implementation owner.
2. Inspect `git status --short --branch`, `git worktree list`, and `git log -3 --oneline`. Preserve another task's uncommitted changes. Fetch when a current remote base is needed; never switch or reset a sibling worktree.
3. Ask Emdash to create a task and its dedicated worktree. Open the selected client there, then copy [the contract](../tasks/contracts/TEMPLATE.md) inside that worktree. Record the actual branch/path, allowed files, criteria, base commit, reviewer, and approvals; Emdash's `emdash/*` names are accepted. One editor per worktree; read-only supporting reviews may share it.
4. Reuse supplied, unchanged instructions and read the completed contract plus relevant architecture/code. Parallel implementation tasks require separate worktrees and explicit file ownership; supporting read-only reviews may share the implementation worktree. Use handoffs to transfer context.

Worktree creation is an Emdash/Git operation, not automated by these files. Create worktrees only for real tasks. Additional worktrees share committed history, not uncommitted changes.

## Select the role

| Work | Client/profile | Limits |
| --- | --- | --- |
| Chat answers | OpenCode `answer-coordinator` (default), or Codex MCP | Simple direct; bounded research/critique for substantive questions |
| Research | OpenCode `researcher` | Read/search only; approve web access |
| Test design | OpenCode `test-designer` | Read/search only; no execution |
| Routine docs, small fixes, test runs | OpenCode `junior-developer` | Approve each edit and shell command |
| Complex implementation | Claude Code | Contract scope and shared approval rules |
| Architecture and independent review | Codex | Review a specified diff/commit against its contract |

Definitions live in `opencode.json`; prompts live in `.opencode/prompts/`. Profiles support direct selection (Tab) and `@researcher`, `@test-designer`, or `@junior-developer`. Use editing profiles in their own worktrees. Built-in unrestricted profiles are disabled. Do not enable `--auto` or broad tool approvals.

Example: "Read AGENTS.md and tasks/contracts/TASK-123-name.md. Research only owned paths and report findings with file references. Return handoff text; do not edit."

Read-only chat questions need no coding contract. See the [answer pipeline](answer-pipeline.md) for `/team`, Codex activation, model stages, and failure reporting. Native task delegation stays denied; the local bridge enforces its fixed read-only sequence.

## Models and credentials

Run `python scripts/check_models.py` before a new OpenCode session or after model changes. It reads the public catalog without a key, verifies zero pricing/tool support, and fails if an endpoint disappears or expires within 14 days. Stop or explicitly choose a verified free replacement on failure; never strip `:free`.

Authentication belongs in OpenCode's user credential store (`/connect`), not Git. Role-specific defaults and runner-ups use exact free OpenRouter endpoints or owner-confirmed free Google/Groq accounts; see [current assignments and guards](model-routing.md). The interactive helper remains on free OpenRouter; bridge workers bind main and helper selections to the same checked candidate to avoid an unrelated provider dependency. OpenRouter price caps and provider fallback restrictions remain; only the bridge can select one reviewed availability runner-up. Direct SDK catalog estimates are retained as estimates, not billed cost.

This configuration was tested with OpenCode 1.19.3 using v1 fields. Newer generations may differ. User configuration, plugins, environment overrides, and MCP clients can change effective behavior. `opencode debug config --pure` loads configuration without inference but may show credentials: inspect only selected non-secret fields and never paste full output into a handoff.

Repository controls cannot impose a cross-provider billing limit. Before approved paid use, set provider limits so aggregate spend, including fees, cannot exceed US$5/month. Existing subscriptions do not authorize new API charges.

## Verify and hand off

Install the pinned development dependencies before testing; Hypothesis is now required for generated boundary tests. Run `python scripts/check_quality.py --security` for compact complete local checks after `python scripts/security_scan.py install` installs the checksum-pinned native scanner. Failed check logs remain available outside Git. See [quality tools](quality-tools.md), [effort limits](agent-efficiency.md) and [curated notes](note-taking.md) when those boundaries are relevant.

```sh
python scripts/validate_repo.py
python -m unittest discover -s tests -v
git diff --check
```

Validation scans tracked files even when ignored, plus non-ignored new files. Findings show paths/types, not secret values. Remove and rotate any real credential; deleting a file cannot erase prior history. Add stack-specific lint/build/tests when introducing product code.

Fill the [handoff](../tasks/handoffs/TEMPLATE.md) with changed paths, exact results, risks, and `uncommitted` or verified hashes. Ask an independent Codex session to review the current diff. Record findings and fixes; mark reviewed and integrated separately.

Reuse owner approval within its scope. Once authorized, commit/push the feature branch and merge only with merge authorization. Verify integration in history, update status/backlog, and retain real commit references. A merge implies no deployment or remote policy change.

## Reuse for a project

Choose a license and stack, document real boundaries, and extend checks to that stack. Keep shared rules short; place specialized guidance near its code. Adapt Serena's indexed folders/language to actual source and deliberately connect it in each client.
