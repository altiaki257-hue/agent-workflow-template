# Direct providers: current operations and pilot evidence

Current automatic assignments and backup rules are authoritative in [free role routing](model-routing.md). MODELS-001 originally used manual pilots; ROUTING-001 superseded its manual-only restrictions. Direct Google/Groq models are now eligible for their reviewed automatic roles, with one classified availability backup in the bridge. Historical claims that direct models cannot hold automatic roles or that all cross-provider fallback is absent do not describe current policy.

## Verify safely

```powershell
python scripts/check_provider_access.py
opencode models groq --pure
opencode models google --pure
```

The Python diagnostic sends only fixed HTTPS model-list GETs with credential headers, rejecting redirects and withholding raw errors. It does not generate answers, verify billing, measure remaining inference quota or prove tool reliability. Missing paginated Google entries can conservatively fail discovery. `check_models.py` separately checks public OpenRouter zero-price/tool/expiry metadata; neither check certifies free-account status.

Direct calls require owner-confirmed free accounts with paid billing disabled, stored outside Git and bound to current key fingerprints for 30 days. Catalog prices can remain positive estimates on a free account; do not relabel them as billing evidence. Interactive model overrides bypass the bridge account guard, so provider billing controls remain necessary. New provider/account/tier changes require verification; never manufacture confirmation to pass a check. The existing aggregate approved paid-inference cap remains US$5/month.

Google free-tier content may be used for product improvement. Use only approved non-sensitive evidence; confirmation of free billing is not permission to export private repository content. For any new-model pilot, start with synthetic supplied evidence, one model at a time, no tool calls or model reassignment. Compare constraints, unsupported claims, output/reasoning usage, latency and reliability, not only prose style or context-window size.

## Historical evidence

On 2026-10-17, owner-confirmed Groq GPT-OSS 120B, Groq Qwen 3.8 27B and Google Gemini 3.1 Flash-Lite passed synthetic generation, function-call and native OpenCode fixture-read probes. This establishes those tested adapters, not general quality, future quotas or billing. Detailed original procedure/results remain in the MODELS-001 handoff (private project record omitted) and Git history. ROUTING-001 (private project record omitted) records the later role promotion. The [dated free-agent review](free-agent-review.md) compares current alternatives without silently replacing assignments.

Sources: [Groq rate limits](https://console.groq.com/docs/rate-limits), [Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Google pricing/data use](https://ai.google.dev/gemini-api/docs/pricing).
