# Agent efficiency and effort

SETUP-002 inspected installed Emdash 1.2.2 without modifying its shipped files. Its Codex adapter extracts `modelId.effort` and supplies it to `codexClient.runTurn`; session configuration stores the user's selected effort. No prompt-difficulty classifier was found in that inspected send path. Automatic reasoning-effort switching is therefore **not configured or verified** in this installation. The current assistant cannot change its own parent turn's reasoning parameter through a prompt rule.

The Codex app-server supports selecting effort per turn, so a host could implement routing. That would require a separate host change with tests; a made-up `auto` configuration value would not establish it. We did not patch the running Emdash binary, change model/provider selections, or incur classifier inference.

Adapt the workflow to the work: answer simple, sufficiently evidenced questions directly; retrieve bounded relevant evidence for ordinary tasks; use deeper investigation and required independent review for uncertain or consequential work. Retain acceptance checks and security boundaries at every level. This changes the amount of work and context used, not the host's actual reasoning setting. Use the available effort selector manually when a different reasoning budget is wanted.

## Configured tools and candidates

The previously discussed list mixed complements and competing alternatives. The compatible core below is installed. Alternatives that add duplicate memory, unverified hooks or services remain deferred; no response to the optional preference question was treated as authorization to replace the established architecture.

| Tool | State and reason |
| --- | --- |
| Ruff 0.17.1 | Existing tool improved with bugbear correctness rules and five findings fixed. |
| basedpyright 1.40.2 | Installed; all `scripts/` checked in basic mode, zero baseline suppressions. Replaces adding a second Pyright checker. |
| Opengrep 1.31.0 | Native checksum-pinned scanner; three existing local rules and positive/negative controls. Replaces vulnerable Semgrep Python environment. |
| Hypothesis 6.170.1 | Installed; generated tests target telemetry privacy and count/number boundaries. |
| Coverage.py 7.16.2 | Installed; branch/statement reports stay outside Git, with compact summaries. |
| pip-audit 2.10.1 | Installed separately; audits isolated dependency profiles. Native scanner integrity is checked separately; see [quality operations](quality-tools.md). |
| RTK OSS 1.0.1 | Installed with verified release SHA-256; explicit command wrappers only. No API proxy or model service. |
| OpenAI Docs MCP | Registered and public initialization verified; reconnect the client for discovery. Full Platform/plugin OAuth connection is not established. |
| Obsidian CLI, core Templates/Properties/Bases, selected skills | Configured and verified; see [notes](note-taking.md). |
| Context7, Serena, Langfuse, Promptfoo, Playwright, Linear | Existing setup retained; this task does not claim fresh verification of every external connection. |
| ast-grep | Deferred until structural searches justify another overlapping retrieval tool. |
| Basic Memory | Deferred: duplicates canonical memory; no additional memory service registered. |
| QMD | Deferred: hybrid/default model downloads conflict with the no-local-model boundary. Keyword-only operation remains an evaluated alternative, not an installed integration. |
| Context Mode | Deferred: automatic host-hook compatibility and interaction with guarded workers are unverified. |
| Superpowers | Deferred: overlaps the existing contracts, tests and review workflow. |
| Dataview, Templater | Deferred alternatives to core Bases/Templates, which cover the configured workflow. |
| Obsidian Local REST API/MCP | Deferred: native CLI works without opening another authenticated service. |
| CodeRabbit | Not subscribed: paid service is outside this setup's existing budget/scope. |
| mutmut | Deferred: native Windows lacks its required fork execution path; no WSL environment was introduced. |
| Betterleaks | Deferred pending reassessment; existing pinned Gitleaks remains the single secret scanner. |

RTK's inspected Codex hook rewrites Bash `tool_input.command`; this session uses `exec_command`/`cmd` through `functions`. Automatic rewriting was not verified, so global hooks and OpenCode plugins were not installed. Run explicit wrappers such as `rtk git status` when helpful. Local tracking is disabled, network telemetry is disabled, and retained failure output uses SQLite with seven-day retention. Use `rtk recall <id>` when a filtered result identifies a retained output. Do not run credential-printing commands through any output recorder. RTK's `gain` counters are output estimates, not measured model-token or answer-quality improvements.

For this repository, `python scripts/check_quality.py --security` gives compact pass/fail rows while preserving complete failed output outside Git. It avoids dumping routine successes into the model context; it does not skip checks. Consult the full failure log before diagnosing a failed check. See [quality tools](quality-tools.md).

References: [Codex app-server](https://learn.chatgpt.com/docs/app-server), [OpenAI Docs MCP](https://developers.openai.com/resources/docs-mcp), [RTK source](https://github.com/rtk-ai/rtk).
