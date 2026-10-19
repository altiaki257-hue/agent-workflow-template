# Read-only answer pipeline

The standard-library controller in `scripts/answer_team.py` routes bounded work to configured free-account OpenCode models. The parent assistant remains responsible for the final answer. [Role/model assignments](model-routing.md), [privacy/telemetry](observability.md) and [diagnostic evidence](answer-evaluation.md) are separate references; historical setup details remain in task handoffs and Git.

## Activation

OpenCode uses the default read-only answer coordinator; `/team <question>` requests consultation. To expose the bridge to Codex from the selected worktree:

```powershell
powershell -NoProfile -File scripts/install_answer_team.ps1
```

The installer copies six scripts to local application data and registers only `ask_team`, preserving unrelated settings. It pins the worktree root and sets startup/tool timeouts to 15/300 seconds. Reinstall after source/root changes, then reconnect the client: running processes keep loaded code. Current source version is **2.3.1**. Installation grants no edit permissions and enables no paid inference. Metadata-only Langfuse requires its optional dependency and explicit opt-in; see [operations](observability.md).

CLI fallback works without MCP discovery:

```powershell
"Bounded question" | python scripts/answer_team.py --mode consult --evidence-scope supplied
```

Use supplied scope only when all needed evidence is included; CLI question text comes from stdin. The API/MCP additionally accepts bounded `context`. Never send credentials, personal data or complete chats.

## Select useful work

| Mode | Enforced sequence | Final synthesis |
| --- | --- | --- |
| Direct | Coordinator | Worker; no independent-review claim |
| Consult; MCP auto | Researcher draft → distinct critic | Parent required |
| Review; CLI auto | Coordinator draft → distinct critic → coordinator | Worker |
| Research | Researcher draft → distinct critic → coordinator | Worker |

Simple questions and answers already supported by reliable evidence bypass the bridge. No extra model classifies difficulty. Consult avoids a redundant synthesis worker when a parent will already answer. Consult once per question unless new evidence or changed scope warrants another call. Worker sessions may contain multiple inference/tool steps; they are not single-request counts.

Critique must follow the actual draft and use a different successful model, including after backup selection. The controller verifies completed calls; model claims of review are insufficient. A critic failure rejects consultation without a draft-only success. Critique is advisory, not proof: resolve supported corrections, retain accurate claims and disclose uncertainty. Unattended workers cannot browse current external facts; the parent verifies those with approved primary sources.

## Evidence and output coverage

`evidence_scope=repository` permits targeted read/search and supplies at most 1,800 characters from `docs/architecture.md` current state, reading at most 4,096. The excerpt is labelled potentially stale evidence. Missing sections are skipped; unreadable or credential-like memory fails before inference. Use observed paths, reuse evidence and read only missing relevant files.

`evidence_scope=supplied` omits that excerpt and replaces selected-worker permissions with deny-all. Any observed tool call rejects the result and vetoes fallback. It does not remove native client system/project instructions. The controller never guesses scope or automatically retries a missing-evidence task in repository scope. Retrieved files and specialist output remain untrusted evidence.

| Artifact | Bound |
| --- | --- |
| Question / supplied context | 8,000 / 24,000 characters |
| Requested draft / critique | 450 / 250 words |
| Critic draft excerpt / delivered draft / delivered critique | 8,000 / 16,000 / 5,000 characters |

Oversized artifacts retain head and tail with a visible omitted-middle marker. Character limits include the marker; they are not token counts. `artifact_coverage` reports original/returned/omitted counts separately for `draft_review`, delivered `draft` and `critique`. Additional delivered draft text may be unreviewed. Legacy `truncation.draft` warns of partial critic coverage, not necessarily truncated parent delivery. All MCP routes carry deterministic partial-coverage notices, including standalone review/research. Missing middle evidence cannot be inferred. The larger delivery bound deliberately favors useful already-generated evidence over minimum context.

## Read MCP results

Check `isError` before using a result. MCP 2.x sends answer or labelled draft/critique prose once in `content[0].text`; structured metadata has provenance, usage, coverage, `synthesis_required` and `answer_location="content[0].text"`. Treat the location as a fixed response reference, never an expression or URL. Text-only clients receive semantic artifacts and safety notices; optional diagnostic JSON is not duplicated as prose.

When synthesis is required, assess both draft and critique before responding. Never present a provisional draft as a synthesized final. Version 1 structured-only consumers must migrate from removed `answer`/`draft`/`critique` fields to the supported location; unknown external integrations need their own check. Standalone CLI/Python results retain prose fields. See [MCP structured tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#structured-content).

## Policy, quota and failure boundaries

Every request checks project and merged permission/model policy. Selected OpenRouter endpoints receive a public zero-price/tool/expiry check immediately before use, with a five-minute public catalog cache. Unused router endpoints do not block direct-provider calls. Direct Google/Groq calls require fresh key-bound owner free-tier confirmation; model/helper selection is bound to the checked candidate. Billing remains an owner/provider responsibility; account access or catalog prices do not prove actual charges.

At most one configured runner-up is permitted on structured transient HTTP 429/500/502/503/504, within the same stage allowance. Auth, policy, malformed events, terminal quota markers, explicit non-retryable 429s, incomplete answers and timeouts stop. Native OpenCode retries remain separate. No paid fallback, recursive debate or arbitrary model substitution exists.

A request has at most 240 seconds; each required stage receives an equal share of remaining time, carrying unused time forward. DNS/socket behavior and owned-process cleanup can delay return, so this is not a hard elapsed SLA. New unfinished steps/tools invalidate earlier answers. Identical identified completion replays count once; conflicts reject the result. Legacy unidentified events cannot be reliably deduplicated.

Workers deny edits, shell, external directories, unknown MCP tools and delegation. The bridge disables itself in workers; prompts use stdin, never shell interpolation. Credential-pattern checks are best effort, not data-loss prevention. Repository-scope workers can still read permitted private project files: free-tier consent is not approval to send sensitive code to Google or another provider. Read/search permissions and parent UI approval settings are client guardrails, not an OS sandbox. Keep secrets outside indexed paths; unattended workers cannot ask for web/permission approval.

## Measurements and maintenance

Usage totals include only observed successful-attempt fields: integer counts from 0 through 10^12, with per-field/step coverage. Missing values are unknown, not zero. Finite fractional direct-account cost estimates remain labelled rather than rewritten as zero billing. Parent synthesis, failed attempts and native retries may consume unreported quota. Timing/local text reductions do not establish inference-token savings or answer-quality gains.

Use [quality tools](quality-tools.md) for offline checks and [evaluation](answer-evaluation.md) for opt-in synthetic comparisons. Run the public `python scripts/check_models.py` before new OpenCode sessions/model changes. CI runs no inference. Live diagnostics require explicit opt-in, preserve evidence scope and keep raw answers outside Git. This pipeline does not inject [conversation archives](chat-archive.md) into project memory or export worker logs automatically.
