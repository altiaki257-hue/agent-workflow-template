# Answer quality and efficiency audit

QA-002, 2026-10-17. This is a small local diagnostic using three synthetic questions, not a general model ranking. Raw answers and reported usage are stored outside Git under local application data; only fixtures and aggregate findings belong in this repository.

## Method

An independent Codex agent answered the same three topics without using the team: repository/CI scope, whether a read-only researcher may run tests, and Git branch/worktree isolation. Its answer-drafting interval was 13 seconds at one-second clock resolution; initial evidence retrieval and context setup were not fully included. No Codex token telemetry or isolated inference latency was available, so those seconds must not be used as an apples-to-apples speed ratio against a complete pipeline run.

The free-model diagnostic uses [versioned cases and criteria](../benchmarks/answer-cases.json), running direct Super versus Super research + Inkling critique. Three cases ran with at most two concurrent cases; within each case direct preceded consult. Provider load, cache warmth, and ordering can affect timing. Consult artifacts are provisional drafts plus critiques: a final answer requires parent synthesis. A model judge may recognize answer style even when candidate labels hide their source. Automated judgments are not human-grounded proof of superiority.

Criteria cover correctness, evidence/limits, useful actionable steps, permissions/uncertainty, and clarity/conciseness. Each dimension receives 0–2 points; a material unsafe or fabricated claim fails regardless of total. For hypothetical questions, unsupported repository citations are unnecessary. Separate assessment of an unmodified draft from assessment of a parent-synthesized answer avoids crediting an unperformed synthesis. This follows the use of explicit criteria and pairwise comparisons in [official evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## Measured runs

The existing active MCP server's three-worker research route completed Q1 in 187.05 seconds wall time (reported 179.33 seconds excluded its preflight). Its output correctly distinguished the workflow template and offline CI from product code, deployment, live model checks, and exhaustive secret detection. This single result does not establish that three workers improve on standalone Codex.

| Case | Direct free model, total seconds | Two-worker consult, total seconds | Direct reported input/output/reasoning | Consult reported input/output/reasoning |
| --- | ---: | ---: | --- | --- |
| Q1 repository/CI | 63.69 | 135.11 | 47,144 / 474 / 795 | 55,040 / 943 / 1,832 |
| Q2 research permissions | 29.19 | 105.80 | 3,388 / 158 / 364 | 26,104 / 565 / 3,382 |
| Q3 worktree isolation | 30.84 | 90.74 | 8,853 / 190 / 639 | 15,207 / 586 / 2,349 |

All six completed. Reported cost was zero; preflight took approximately 6.0–6.6 seconds per run. Consult additionally reported cache-read tokens of 63,808 / 17,280 / 8,320. Token categories are reported separately rather than asserting a billing-equivalent total. Consult median latency was 105.80 seconds versus 30.84 for direct free inference; parent synthesis is additional. Configured tool-step limits are not exact request ceilings: Q1 research reported 13 finish events despite configured steps 12, including terminal behavior.

## Answer comparison

A second independent Codex agent judged randomized A/B labels without reading the authorship key. The final consult candidates were synthesized by the parent Codex after reading actual research/critique; they are not raw free-model drafts. Scores, out of ten across the five criteria above, were:

| Case | Standalone Codex | Consult + parent Codex synthesis | Preference |
| --- | ---: | ---: | --- |
| Q1 | 9 | 10 | Consult/parent: explicit limitation about current uncommitted remote CI |
| Q2 | 10 | 10 | Tie |
| Q3 | 10 | 10 | Tie |

This is one judge, three easy questions, no human labels, and a ceiling effect. Both systems knew the repository's shared rules, and workers could read versioned benchmark criteria; Q3 actually cited them. This is an engineering diagnostic, not a held-out benchmark or evidence that teams generally outperform Codex.

Material observations matter more than the one-point difference:

- Direct free Q1 incorrectly claimed there was no CI configuration, despite its existence. The consulted researcher found CI; the critic failed to verify it because it repeatedly invented `/workdir/...` paths. A denied path is not evidence of absence. Root checked synthetic-session tool errors and corrected the path guidance before a targeted retest.
- Q2 research speculated that these tests might be flaky/noisy. Critique challenged that claim; parent synthesis removed it and retained the meaningful value of workflow tests. Some critique objections incorrectly treated absence from AGENTS.md as refutation of general technical risk, so the parent did not accept critique automatically.
- Q3 research implied unstashed changes would be lost on a normal branch switch. The critic missed this; parent Codex corrected it using [Git's switch documentation](https://example.com/external-reference), which describes aborting a switch that would lose local changes unless explicitly told otherwise. This demonstrates why a completed critique is not proof of correctness.

For these questions, standalone Codex was already strong. Use free workers for bounded evidence gathering and useful independent challenge; keep the main assistant responsible for reasoning and final synthesis. Simple/known questions should bypass the team. Do not pay the latency cost merely to claim that multiple agents participated.

## Targeted regression after fixes

Q1 was reused to debug the observed retrieval defects, so these are tuned regression checks rather than unseen benchmark results. With explicit relative-path/CI-read guidance, direct free inference found CI in 34.84 seconds and consult completed in 101.41 seconds; the critic successfully read the workflow. Both still described the template too broadly as Emdash's own framework. Adding one bounded `docs/architecture.md#current-state` memory excerpt produced a correct template/CI answer in 41.17 seconds, with 3 finish events and 10,435 reported input tokens (plus 4,576 cache-read), versus the original incorrect direct answer's 12 events and 47,144 input tokens. No general latency or quality improvement percentage is justified by these single samples.

## Improvements and boundaries

- MCP auto now uses two-worker consult, followed by parent synthesis, removing one duplicate free-worker session. Critique is retained. CLI standalone review/research still use three workers.
- Total time includes preflight; per-stage steps/tokens/cache/cost expose actual work rather than confusing sessions with requests. Usage is client/provider-reported, not billing proof.
- A bounded current-state memory excerpt reduces repeated project rediscovery; workers use relative/observed paths and cannot treat denied/empty searches as proof of absence. Documentation is labelled potentially stale evidence, not an overriding instruction.
- At this historical OPT-002 stage, returned draft was exactly the bounded text seen by the critic. OPT-004 supersedes delivery with separate critic/parent coverage and bounded head/tail artifacts; see [current pipeline](answer-pipeline.md). Consult still exposes no final `answer` field; the parent must resolve critique.
- At this historical QA-002 snapshot, safety validation rejected agent-specific paid-routing overrides and unknown enabled MCP servers, with no retries or paid fallback. Current routing subsequently added owner-confirmed direct accounts and one guarded availability runner-up; see [current routing](model-routing.md).
- Independent review also corrected archive data-loss/filtering/cache defects and owned automation transition checks. See the QA-002 handoff for exact checks and remaining configuration actions.

At the QA-002 snapshot, the parent Codex client was observed in Emdash full-access/auto-approval mode, the installed bridge was 1.1 and the active process still ran 1.0. These are historical observations. Worker safety does not create UI enforcement for the parent. Account quota/billing dashboards and future free-endpoint availability cannot be certified from local checks. Reconnect after installation to load current bridge code.

## Current implementation note

The historical results above retain their original versions and model assignments. ROUTING-001 and CONTROLLER-001 supersede that runtime; OPT-002 adds supplied-evidence scope and reduces repeated prompts. The separate OPS-001 experiment below adds current synthetic evidence; broader quality or token-saving claims still require controlled, human-reviewed comparisons. See the [current pipeline](answer-pipeline.md) and OPT-002 handoff (private project record omitted).

OPT-003 makes evidence scope explicit in benchmark cases: Q1 permits repository retrieval, while the self-contained Q2/Q3 cases use supplied evidence without tools or injected project identity. Older measurements above used repository scope for all three and are not directly comparable to future runs. This prevents those hypothetical cases from retrieving their versioned criteria, but native client instructions can still contain shared project rules; no held-out benchmark or general token-saving percentage is claimed.

## OPS-001 fresh comparison (2026-10-18)

[Five new cases](../benchmarks/fresh-answer-cases.json) exercised partial usage, fallback independence, deadline arithmetic, conflicting evidence/authority and safe archive review. The live harness used supplied evidence without worker tools, seed `20261018`, sequential execution and a shuffled case order with alternating first route (3/2 counterbalance). Rubrics were never sent to workers. All ten attempts completed; no bridge availability fallback occurred. Script/controller/case hashes, schedule, timestamps, unique row IDs and incremental recovery records are retained with raw synthetic results outside Git under the user-local `EmdashAnswerTeam/benchmarks` directory.

A fresh-context parent saw only supplied facts and each actual consult draft/critique before producing five final syntheses. It saw neither direct answers nor rubrics/usage/model labels. The offline exporter linked these finals to their consult rows, then randomized pairs with seed `18102026`. A separate fresh-context judge received only the blind packet. The private route key was read after judgment. Scores use correctness, evidence/uncertainty and usefulness, each 0–2; material unsafe/fabricated guidance fails regardless of points.

| Case | Direct worker / 6 | Consult + parent / 6 | Blind preference |
| --- | ---: | ---: | --- |
| F1 partial usage | 5 | 6 | Consult + parent |
| F2 fallback/independence | 6 | 6 | Tie |
| F3 deadline arithmetic | 5 | 6 | Consult + parent |
| F4 evidence/authority | 3 | 6 | Consult + parent |
| F5 archive safety | 0; hard failure | 6 | Consult + parent |
| Total | 19 / 30 | 30 / 30 | Four preferences, one tie |

The root manually confirmed that F3's direct answer exceeded the 180-word bound (223 whitespace-separated words). F5's direct rewrite used a fixed temporary filename that could truncate an existing file; the case excludes concurrent mutation, so race scenarios are outside this assessment. It also incorrectly claimed a propagated write exception would still reach the following unlink. These concrete defects support the safety finding; the model judge's opinion alone is not proof. F4's score reflects the judge's assessment of unsupported deployment/CI inferences and unnecessary authorization discussion, which remains advisory.

| Reported successful-worker measurement | Direct (five runs) | Consult (five runs; workers only) |
| --- | ---: | ---: |
| Median wall seconds | 17.45 | 36.25 |
| Input tokens | 10,298 | 20,491 |
| Output tokens | 1,476 | 2,580 |
| Reasoning tokens | 1,958 | 5,824 |
| Cache read / write | 0 / 0 | 0 / 0 |

Each listed worker token field was observed in all five runs per route. These categories are kept separate; no billing-equivalent sum is asserted. Parent token usage and synthesis latency were unavailable and remain `null`, making combined consultation totals unknown. Native internal retries are not separately observed. Consultation used more worker tokens here; this experiment demonstrates no end-to-end token savings.

This is one model judge, five synthetic cases, no human labels and possible style recognition despite hidden route metadata. It compares a direct worker with two workers plus an additional parent, and cannot isolate the contribution of critique from that extra synthesis. It establishes neither general superiority nor a model ranking. Failures, unknown usage and historical results must remain visible in future comparisons. See the MEASURE-001 procedure (private project record omitted) and OPS-001 verification (private project record omitted).

## OPT-004 diagnostic hardening

Explicit evidence scopes in cases, worker rows and worker results must agree before blind pairing; absent legacy fields remain accepted without inventing scope provenance. The deterministic relationship checks now reject a bounded family of prefixed contradictory recommendations, including advice to report zero after admitting usage is unknown. Negated and descriptive quoted claims remain controls. These rules still do not understand arbitrary language or establish model quality. No fresh live quality/token benchmark was run for this refinement.
