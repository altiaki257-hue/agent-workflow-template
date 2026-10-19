# Free-agent review — 2026-10-19

## Decision

Keep the current automatic assignments until a bounded task-specific pilot demonstrates a better replacement. **Gemini 3.5 Flash-Lite** is the first researcher candidate to test on the already approved Google provider. **Gemma 4 31B free on OpenRouter** is a second manual candidate for concise reasoning. Neither has been promoted, granted permissions or sent repository contents. No new account, paid subscription, provider or local model service was added.

There is no verified provider that simultaneously offers better task quality, higher sustained free quota, identical privacy terms and demonstrated native tool reliability for this project. Several widely repeated free-tier lists are stale. Model weights being free does not make hosted inference unlimited, and a large context window is not a free token allowance.

## What is installed/configured

OpenCode has five restricted roles, not five independent model subscriptions. The researcher and coordinator permit at most 12 steps, critic 6, test designer 10 and junior 12. Every extra tool/read step can add another model request and repeat context. Step limits are ceilings, not targets; do not lower them blindly when evidence retrieval is needed.

| Role | Current model | Decision |
| --- | --- | --- |
| Researcher | Google Gemini 3.1 Flash-Lite | Retain; test 3.5 Flash-Lite with supplied synthetic evidence before promotion. |
| Coordinator | Groq GPT-OSS 120B | Retain fast synthesis baseline; exact benchmark reasoning settings differ from this adapter. |
| Critic / junior | Groq Qwen 3.8 27B | Retain constrained roles; reasoning quality can cost substantial output/reasoning quota. |
| Test designer / reviewed backup | OpenRouter North Mini Code free | Retain; specialized coding evidence and previous small local sample are useful but not a broad ranking. |
| Manual selections | Nemotron Ultra, Super, 3.5 Lightning, Inkling free | Current public catalog still lists them. Earlier bounded probes were incomplete/unavailable; do not equate availability with a quality win. |

Exact IDs and guard pairs remain in `opencode.json` and `ROLE_MODELS`. A fresh public catalog check passed for all configured OpenRouter endpoints. The catalog currently lists additional tool-capable free variants, including Gemma 4 31B/26B, Inkling Small, Nemotron 3.5 Super VL and Xing 4.0. Short-lived Laguna variants expire October 31 and are poor durable defaults. No catalog-only finding establishes account capacity or reliable answers.

## Quotas: compare like units

| Provider | Verified current offering | Consequence for this workflow |
| --- | --- | --- |
| Groq | Public free-plan table lists GPT-OSS 120B and Qwen 3.8 27B at 30 RPM, 1,000 RPD, 8,000 TPM and 200,000 TPD. Organization exceptions may apply. | Existing direct roles remain attractive. An 8k/minute cap can bottleneck repeated context well before the daily budget; these are provider table limits, not a fresh account entitlement audit. [Official limits](https://console.groq.com/docs/rate-limits). |
| Google API | Both 3.1 and 3.5 Flash-Lite have free input/output entries. Exact RPM/TPM/RPD depend on project/model and are shown in AI Studio, not a universal current public quota. | Candidate upgrade is plausible; more free tokens or better answers are not established. Free API content may improve products. [Pricing/data use](https://ai.google.dev/gemini-api/docs/pricing), [quota rules](https://ai.google.dev/gemini-api/docs/rate-limits). |
| OpenRouter | Read-only account metadata returned a **50 free-model requests/day ceiling** for this account. The public table uses credit-history tiers; account-specific ceiling was checked without logging credentials, labels, balances or usage counters. | This is a request limit, not a token budget and not 50 requests per free model. Tool steps and retries can consume it. Normal Google→Groq consultation uses direct quotas; router backups/test-design consume the router allowance. [Official limits](https://openrouter.ai/docs/api_reference/limits). |
| NVIDIA hosted NIM | Official product page offers free prototyping/development/testing access. A universal current token/day guarantee was not verified. | Worth evaluating for a specific hosted model if terms and account limits fit; no claim of an unlimited production replacement. No local NIM server is proposed. [Official offering](https://example.com/external-reference). |
| Cloudflare Workers AI | 10,000 neurons/day on Workers Free; some frontier models require paid billing or prepaid credits. | Neurons are model-weighted compute units, not tokens. Compare a concrete eligible model/workload; no general quota/quality upgrade is established. [Current pricing](https://example.com/external-reference). |
| Mistral | Studio documentation confirms a default rate-limited free playground mode. | Playground access does not establish an API token/day entitlement. API account quotas and candidate quality need verification before adding it. [Official documentation](https://docs.mistral.ai/getting-started/quickstarts/studio/test-model-playground). |
| Cerebras | Current Free Trial: $5 credits after payment-method verification, expiring after 30 days; documentation explicitly says no renewing free tier. | Not a permanent free-capacity alternative. [Current terms](https://example.com/external-reference). |
| Hugging Face routed inference | Current table gives free users no monthly credits; paid subscriptions include credits. | Older claims of a recurring free-user allowance are stale. [Current pricing](https://huggingface.co/docs/inference-providers/pricing). |
| GitHub Models | Official documentation states the service retired July 30, 2026. | Not an available free alternative; GitHub Copilot is a separate product. [Retirement](https://docs.github.com/en/github-models). |

New API keys/accounts do not create legitimate extra capacity for the same quota scope. No cycling accounts, credits purchase, billing activation or provider-term bypass is proposed. Google quotas remain account-specific and unverified here; do not infer them from browser subscriptions, batch quotas or old screenshots.

## Quality evidence and its limits

Independent **Artificial Analysis Intelligence Index v4.3.2** pages currently report Qwen 3.8 27B at xhigh **34**, GPT-OSS 120B at high **12**, and Gemma 4 31B reasoning **15**. These measure evaluated variants/settings, not this exact Groq/OpenCode adapter or critic accuracy. The same pages report benchmark output totals of 200M, 84M and 49M respectively; these are full evaluation-run totals, not tokens per answer, daily quotas or a local savings estimate. They suggest a quality/verbosity tradeoff worth testing, not a safe automatic reassignment. [Qwen measurement](https://example.com/external-reference), [GPT-OSS measurement](https://example.com/external-reference), [Gemma measurement](https://example.com/external-reference).

Cohere publishes North Mini Code SWE-bench Verified 67.6, SWE-bench Pro 40.2 and Terminal-Bench 2 36 under specified agent harnesses. These are **vendor-reported agentic coding evaluations**, not independent review/research scores and not comparable directly to the intelligence-index scale. Its prior local test-design result supports retaining it while broader evidence is gathered. [Model card and harness notes](https://huggingface.co/CohereLabs/North-Mini-Code-1.0).

Google documents 3.5 Flash-Lite as a low-latency subagent/document-processing model with function calling, which matches the researcher workload. This is a provider positioning claim, not a verified improvement over 3.1 in this repo. [Current model specification](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite). Direct Artificial Analysis pages for these Gemini variants could not be retrieved; no missing score was invented. LiveBench pages were reachable but their dynamic table could not be extracted reliably; stale search snippets were excluded from numeric comparisons. Third-party directories helped locate candidates, while official pages determined quota/availability claims.

## Pilot that would justify changing a role

Use new, non-sensitive supplied-evidence cases covering constraint following, supported corrections, refusal to invent facts, portable code reasoning and concise research. Counterbalance candidate order; use the same prompts/bounds and at least several independent cases/repeats. Evaluate actual final answers, not provisional drafts. Keep the critic distinct, inspect false positives/omissions, record output and reasoning tokens separately, and preserve missing telemetry as unknown. Include timeout/quota/tool-call reliability before assigning real work.

Do not optimize a benchmark percentage while increasing rereads, reasoning tokens or unsupported certainty. Free-tier confirmation permits account use, not sensitive-code export; repository-scope Google workers can read permitted files, and credential regexes do not classify business/private data. The concrete improvement now is less redundant context and accurate partial-review warnings, with current routing retained until such a pilot is useful and within existing guards.

## Fresh consultation check

A new supplied-evidence draft/critique consultation reviewed this recommendation. The parent found unsupported premises: it described Google research as private, generalized some paid-model restrictions to whole providers, and objected that benchmark-run totals were being used as quotas despite the supplied evidence explicitly separating them. Those objections were rejected rather than adopted. The critic usefully called for reasoning-token/reliability measurements but did not correct every premise. This is one non-blinded advisory observation, not a model ranking or a controlled benchmark; it reinforces parent verification and accurate privacy boundaries.
