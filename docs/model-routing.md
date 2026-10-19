# Free role routing

ROUTING-001 promotes the owner's confirmed free Google/Groq accounts into automatic roles. All inference stays hosted. Claude still owns complex implementation, Codex architecture and independent code review, and Emdash separate task worktrees. These external roles are unchanged.

The [2026-10-19 free-agent review](free-agent-review.md) checks current quotas and alternatives. It retains these assignments and identifies candidates for controlled evaluation; provider lists and benchmark scores do not automatically update policy.

## Assignments

| OpenCode role | Default | Runner-up | Selection rationale |
| --- | --- | --- | --- |
| Answer coordinator | Groq GPT-OSS 120B | OpenRouter North Mini Code free | Reasoning/synthesis first; alternate with strongest combined sample |
| Researcher | Google Gemini 3.1 Flash-Lite | Groq GPT-OSS 120B | Concise evidence summaries; stronger reasoning alternate |
| Answer critic | Groq Qwen 3.8 27B | OpenRouter North Mini Code free | Correct targeted critique without false positives; strong combined alternate |
| Test designer | OpenRouter North Mini Code free | Groq GPT-OSS 120B | Strongest sampled retry-test plan; reasoning alternate |
| Junior developer | Groq Qwen 3.8 27B | OpenRouter North Mini Code free | Correct sampled path implementation with low latency; correct alternate |

`scripts/validate_repo.py::ROLE_MODELS` is the reviewed primary/runner-up table. `opencode.json` must match its primary assignments and exact allowlists. Generic/helper models use free North Mini Code. Eight unique models remain configured; four appear in these assignments. Ultra, Super, Lightning and Inkling remain available manually, but are not preferred fallbacks after incomplete/unavailable bounded probes. These are provisional operational selections, not proof of global model superiority. Google is for non-sensitive research/documentation; do not use it to review security code without a stronger critic.

## How backups work

The answer-team bridge automatically tries at most one configured runner-up per stage, only after a structured HTTP 429, 500, 502, 503 or 504 error. Both attempts share a stage allowance within the original 240-second request budget; CONTROLLER-001 reserves time for required downstream stages and carries unused time forward. Authentication, policy, missing/expired free-tier confirmation, unknown failures, incomplete output and timeouts stop immediately. There are no paid variants or arbitrary provider substitutions. OpenCode's own internal request retry behavior is separate; the bridge bounds worker attempts and process lifetime, not every SDK network request.

QA-003 additionally stops fallback for explicit non-retryable 429s and exact documented terminal quota/credit markers in bounded structured response bodies. Error prose alone does not establish exhaustion. Ordinary rate limits, including Google's broad `RESOURCE_EXHAUSTED`, can remain transient. Installed OpenCode 1.19.3 has its own hardcoded retry policy without a verified supported override; this fix prevents a redundant bridge backup after its terminal error arrives, not those internal delays. Raw provider messages/bodies remain withheld.

The critic excludes the actual successful draft model, including when a draft used its backup. If no distinct available critic remains, consultation fails rather than claiming review. Successful stages report the selected model, attempts and timing. Failed attempts may consume unreported quota; aggregate usage covers successful attempts only. A draft is still provisional until parent synthesis resolves the critique.

Interactive OpenCode does not automatically read the Python backup table. Explicit commands preserve the same role and permissions:

```text
/answer-coordinator-backup <question>
/researcher-backup <question>
/answer-critic-backup <question>
/test-designer-backup <task>
/junior-developer-backup <task>
```

Junior edits and every shell command still require approval. Automatic implementation/test execution failover is deliberately absent. The backup commands invoke the model explicitly through OpenCode; they bypass the bridge's account-confirmation guard, so provider billing controls remain required. A single critic command cannot establish independence from an unspecified draft.

## Free-account guard and privacy

The owner explicitly confirmed free tiers and disabled paid billing for Groq/Google. A local record at `%LOCALAPPDATA%/EmdashAnswerTeam/free-tier-accounts.local.json`, outside Git, binds that confirmation to SHA-256 fingerprints of the current credentials for 30 days. The bridge refuses direct-provider calls if the record is absent, stale, future-dated or mismatched. Keys stay in OpenCode's user store/environment; the guard never logs them. Environment aliases are bound to the checked credential before launching a worker. Reconfirm status and refresh the local record after key/account changes or expiry; do not fabricate a confirmation just to pass a check.

This is an owner assertion, not a billing API audit. OpenCode's catalog may report positive estimated dollar costs for free-account requests. Those estimates are retained and labelled, not rewritten to zero or treated as billed charges. OpenRouter calls still require explicit `:free` IDs, zero price limits and disabled provider fallbacks. No paid inference mode is added; any later paid usage needs approval and the existing aggregate US$5/month limit.

Google's free API data-use terms allow product improvement; send only approved non-sensitive evidence. No keys, credentials, personal data or private production contents in prompts. Read/search permissions are client guardrails, not an OS sandbox. The new tests used only synthetic data. Provider quotas and future account changes can still stop service.

## Evidence and limitations

On 2026-10-17, one identical synthetic four-part prompt tested evidence discipline, retry tests, a path-containment review and a Python example. Source answers and metrics stay outside Git in the local `EmdashAnswerTeam/benchmarks/routing001-role-probes.json` file. Human/primary-agent assessment, not a model assigning itself a score:

| Model | API seconds | Observed result |
| --- | --- | --- |
| GPT-OSS 120B | 3.30 | Correct evidence/code and useful review; one test incorrectly retried the same endpoint |
| Qwen 3.8 27B | 0.94 | Correct evidence/path code; ambiguous and incorrect retry tests |
| Gemini 3.1 Flash-Lite | 4.36 | Correct evidence and useful tests; path implementation failed portable containment/root equality |
| North Mini Code | 17.16 | Correct evidence, constraint-focused tests, containment review and code |
| Super | 38.03 | No final text within 1,800 output tokens; reasoning consumed the cap |
| Inkling | 32.67 | No final text within that cap; not scored for quality |
| Ultra | 0.62 | Request unavailable; not scored for quality |
| Lightning | 45.12 | Timed out; not scored for quality |

A second targeted critique of the same synthetic draft exposed a false-positive objection from North and an invented backup-identity rule from GPT-OSS. Qwen correctly preserved accurate statements and identified a missing non-retryable-status test, so it became the default critic. It still missed the backup-identity gap; parent synthesis must resolve omissions and false positives. Raw comparisons stay in `routing001-critic-comparison.json` outside Git.

The direct API probes are not native OpenCode latency comparisons, repeated trials, broad coding benchmarks, or future availability guarantees. Prior MODELS-001 tests separately verified native OpenCode tool calls for all three direct models. See the ROUTING-001 handoff (private project record omitted) for the new end-to-end consultation and offline regression results. Researcher/critic scopes and their prompts continue to matter; model choice cannot replace evidence or independent code review.

After bridge script changes, run `scripts/install_answer_team.ps1` and reconnect Codex/OpenCode to load the current implementation. Verify the reported version rather than assuming an existing process reloaded. CI remains offline; live quotas and billing are not checked there.

Sources: [OpenCode agent models](https://opencode.ai/docs/agents/), [command model overrides](https://opencode.ai/docs/commands/), [Groq coding models](https://console.groq.com/docs/coding-with-groq), [Groq quotas](https://console.groq.com/docs/rate-limits), [Google pricing/data use](https://ai.google.dev/gemini-api/docs/pricing).

Final live verification: Gemini -> Qwen consultation completed in 46.34 seconds; a fresh installed GPT-OSS -> Qwen -> GPT-OSS review/synthesis completed in 45.49 seconds. Seventy-seven offline tests ran with 76 passing and one existing Windows symlink-privilege skip. These checks establish the tested workflow, not universal answer accuracy.
