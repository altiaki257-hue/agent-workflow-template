# Quality tools

The local toolchain is configured by [Ruff](../ruff.toml), [pre-commit](../.pre-commit-config.yaml), and [pinned development dependencies](../requirements-dev.txt). These are development tools; the answer controller still needs only Python's standard library.

## Installation and local checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pre_commit install --allow-missing-config
python -m pre_commit run --all-files
python -m pre_commit run gitleaks-history --hook-stage manual --all-files
python -m unittest discover -s tests -v
```

Pre-commit downloads isolated, versioned Ruff 0.17.1, actionlint 1.7.12 and Gitleaks 8.30.1 environments. Its Go language support bootstraps Go when needed; a system Go install is unnecessary. First installation requires network access and can take several minutes. The local repository-policy hook runs existing offline validation on every commit. Ruff checks correctness rules E4/E7/E9/F plus bugbear B without automatic fixes or formatting. Actionlint's optional shellcheck and pyflakes subprocess integrations are disabled consistently locally and in CI; workflow syntax and expression checks remain enabled.

SETUP-002 adds basedpyright 1.40.2 (`pyrightconfig.json`, all scripts, basic mode, no baseline), Hypothesis 6.170.1 boundary properties and three local security rules. OPT-005 replaces the Python Semgrep tool with checksum-pinned native Opengrep 1.31.0 to remove its vulnerable MCP SDK dependency. Development requirements include the optional observability SDK so its interface is type-checked; importing the controller still needs only the standard library. Install the scanner explicitly; later checks verify its checksum and never install automatically. Windows x64 and Linux x64/arm64 assets are supported; other platforms fail closed. Binaries live outside Git under `%LOCALAPPDATA%/EmdashSecurity/opengrep/1.31.0` on Windows or `~/.cache/EmdashSecurity/opengrep/1.31.0` on Linux.

```powershell
basedpyright
python scripts/security_scan.py install
python scripts/security_scan.py controls
python scripts/security_scan.py scan
python scripts/check_quality.py --security
```

The three Semgrep-compatible rules check shell execution, dynamic Python execution and explicit TLS-verification bypasses. Positive/negative controls prove the selected patterns work; this narrow scan is not a complete vulnerability audit. Scans use an explicit local rule file and disable update checks; no login, registry rules or source upload is needed. The native CLI has no `--metrics` option; the old flag is not passed. CI runs the controls and scan, type checks and generated boundary tests. Hypothesis is a test dependency, not a runtime dependency.

The compact runner executes policy, Ruff, types and the full unittest suite, with optional security controls/scan. It prints one status row per check, preserves a complete failed log in a temporary directory outside Git, deletes successful logs and returns failure if any check fails. Each check has a 180-second limit. Failure logs may contain repository output: inspect them locally and remove them after diagnosis. The runner does not perform live inference or install missing tools.

Git worktrees normally share the hook directory. `--allow-missing-config` allows sibling worktrees without this configuration to continue committing. Do not overwrite a pre-existing hook; pre-commit migration mode preserves it. Hook installation does not stage, commit or publish changes.

Gitleaks checks staged changes at commit time with redaction and reduced log output. The separate manual history hook scans all locally available refs; fetch complete history before treating it as a full repository-history baseline. CI uses `fetch-depth: 0`. Existing policy validation scans current tracked and non-ignored files, including uncommitted files. These complementary checks do not certify that every secret pattern is detectable. Report only the path and secret type if a finding occurs; rotate any real credential.

Gitleaks currently receives security patches only. It is retained as the initial, pinned scanner with established CLI/hooks. Reassess Betterleaks before adopting new scanner features; do not install both by default. See the [upstream maintenance notice](https://github.com/gitleaks/gitleaks).

CI retains the Windows/Linux policy tests. A dedicated quality job checks Ruff, actionlint and all available Git history; the aggregate `repository-policy` requires both jobs to pass. These checks passed remotely before [PR #9](https://github.com/example-org/agent-workflow-template/pull/9) merged as `8baa126`. The private repository's account plan blocks branch protection (HTTP 403); successful checks are verified procedurally before merging.

## Promptfoo diagnostics

The [configuration](../evals/promptfooconfig.yaml) contains [ten synthetic cases](../evals/cases.json) and two routes. [The adapter](../scripts/promptfoo_provider.py) defaults to fixture outputs and makes no model call. Both routes reuse fixtures offline to test configuration/provider/assertion plumbing; twenty passing fixture evaluations establish no model-quality gain. [Deterministic Python assertions](../scripts/evaluation_assertions.py) check required relationships and selected explicit contrary claims. Regression controls include alternate correct phrasings and unsafe answers that passed the previous single-keyword checks. These bounded phrase checks can still produce false positives or false negatives; human review against case intent remains necessary for live outputs.

```powershell
npm install -g promptfoo@0.124.1
python scripts/run_promptfoo.py
```

The [runner](../scripts/run_promptfoo.py) verifies the CLI version, disables telemetry, sharing, caching, update checks and Promptfoo result-database writes, and sends output to the existing user-local benchmark folder outside Git. Use the runner rather than invoking Promptfoo directly. It overrides an inherited live-mode variable to keep its default offline. It invokes Node directly on Windows to avoid command-shim interpretation of file paths.

Live evaluation is an explicit operation and defaults to one case, one request at a time:

```powershell
python scripts/check_models.py
python scripts/run_promptfoo.py --live --first-n 1
```

The direct route calls the existing controller once; review runs draft, independent critique and standalone synthesis. Both use supplied evidence and existing free-provider/account/policy/deadline guards. Consult drafts are rejected as evaluation targets. No separate inference SDK, model assignment, paid grader or fallback is introduced. A full run of ten cases requires `--live --first-n 10`; free quota can still be consumed. Provider failures remain errors rather than being scored as successful answers.

Reported usage, its coverage, stage timings, selected models and catalog-cost basis stay in response metadata. Unknown usage remains unknown; catalog estimates are not exposed as actual billed cost. Promptfoo's aggregate zero-token/cost display is not evidence of zero live usage: this custom adapter retains controller measurements and completeness in metadata rather than native Promptfoo token/cost fields. Parent consultation synthesis is a different route and is not benchmarked here.

## External connections and remaining actions

- **Linear:** On 2026-10-18, owner-authorized [AI-5](https://linear.app/example-workspace) was created, read, updated with a synthetic verification marker and marked Done. Final read-back confirmed the marker and completed state. This verifies one isolated round trip; broader automatic writes remain off. The Emdash tracker connection is separate, and plugin availability can differ by client/session.
- **Langfuse:** The optional metadata-only exporter uses SDK 5.0.2 in a separate process. An actual synthetic root/stage trace was retrieved on 2026-10-18 and checked against exact allowed metadata, parentage and empty input/output/user/session fields. Credentials remain in Windows user environment settings; no keys are copied into Codex configuration. Delivery is best effort and does not establish complete billing/token coverage or retention policy. See [setup, privacy and smoke verification](observability.md).
- **Publication/review:** QUALITY-001/OPT-003 were independently reviewed and merged through PR #9 after platform/quality checks passed. OPS-001's handoff (private project record omitted) records the separately reviewed completion work and its integration evidence.

Sources: [Ruff integration](https://docs.astral.sh/ruff/integrations/), [pre-commit](https://pre-commit.com/), [actionlint usage](https://github.com/rhysd/actionlint/blob/main/docs/usage.md), [Promptfoo Python providers](https://www.promptfoo.dev/docs/providers/python/), [Promptfoo telemetry controls](https://www.promptfoo.dev/docs/configuration/telemetry/), [Langfuse masking](https://langfuse.com/docs/observability/features/masking).

## Branch coverage and dependency auditing

Coverage.py 7.16.2 is pinned in development requirements. pip-audit 2.10.1 is pinned separately in `requirements-audit.txt` and installed locally as an isolated uv tool. CI runs the existing platform test suite under branch coverage once, with its database in runner temporary storage; no arbitrary percentage gate or exclusion baseline was added.

Reproduce auditor installation with `uv tool install pip-audit==2.10.1`; keep it separate from the development/observability environment.

```powershell
python scripts/quality_metrics.py coverage
python scripts/quality_metrics.py dependencies
```

Both commands print compact JSON and retain full logs/JSON in a new external temporary directory. An explicit `--output-dir` must be new/empty and outside Git worktrees. Failed tests cannot yield passing coverage; missing/skipped/malformed dependency results fail the audit. Use the full reports for missing-line/branch details and remediation; counts alone are not proof of test quality.

Dependency audits resolve development and auditor requirements separately, matching their isolation boundaries. Opengrep is a native release binary, outside pip-audit coverage; checksum verification is not a native vulnerability scan. The scheduled/manual dependency workflow contacts package/advisory services, runs no inference and applies no automatic upgrades or ignored-vulnerability exclusions. Ordinary CI remains independent of live advisory availability. Results depend on current advisory data, Python/OS markers and resolution; they are not a cross-platform locked-transitive audit or a scan of every installed uv tool environment. Local source reports stay outside Git and are not sent to model providers.

Baseline measurement on 2026-10-19: 84.84% statements, 78.33% branches over scripts, excluding subprocess execution not instrumented by the run. Follow-up security/failure regressions and final measurement are recorded in the OPT-005 handoff. The initial development resolution (43 packages) and auditor resolution (26) had no known findings; the retired security resolution (66) flagged one vulnerable package. Final results are in the handoff; these counts describe dated resolution snapshots.

**Resolved tool dependency finding:** Semgrep 1.181.0 still pins `mcp==1.29.0`, affected by `CVE-2026-59951`. Fixed MCP releases include 1.30.0 and 2.2.0, incompatible with that exact pin. The vulnerable isolated Semgrep environment and `requirements-security.txt` were removed; CI and local checks now use [Opengrep 1.31.0](https://github.com/opengrep/opengrep/releases/tag/v1.31.0), preserving the existing rules and positive/negative controls. No dependency override, downgrade or ignored advisory is used. The scanner installer pins official asset SHA256 digests before execution and preserves existing files on mismatch. This removes the identified Python SDK dependency; it does not certify the native scanner as vulnerability-free. [Upstream fix](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v1.30.0), [advisory](https://example.com/external-reference).
