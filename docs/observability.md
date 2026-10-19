# Optional metadata observability

OBS-001 and OPS-001 keep answering on the standard-library controller. The Langfuse SDK is used only in an explicitly enabled exporter child process. Install its optional pinned dependency with `python -m pip install -r requirements-observability.txt`.

## Enable and verify

Keep `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL` in local environment settings, never Git or chat. The endpoint must be HTTPS. `ANSWER_TEAM_LANGFUSE=1` opts a process into tracing; unset it or set it to `0` to disable export. The controller can read these named credential settings from the Windows user environment when an existing parent process has not inherited them.

For the installed Codex bridge, run:

```powershell
powershell -NoProfile -File scripts/install_answer_team.ps1 -EnableTelemetry
```

The installer copies the optional exporter and writes only its opt-in flag under the owned MCP server's environment. It preserves unrelated servers/settings and stores no Langfuse key in Codex configuration. Reconnect the client to load the copied bridge. Running the installer without the switch preserves an existing opt-in; change that server's `ANSWER_TEAM_LANGFUSE` value to `0` to disable it.

To test delivery from a terminal that has inherited the credential settings:

```powershell
$env:ANSWER_TEAM_LANGFUSE='1'
python scripts/answer_telemetry.py --smoke
```

Only `status: verified` establishes that the synthetic request/stage observations were retrieved and matched their IDs, parentage, metadata and absent content/identity fields. `submitted` is an export attempt, not delivery proof. The smoke uses SDK 5's observations API; legacy trace-get methods are absent in the installed SDK. Eventual consistency is handled by bounded polling.

## Privacy and failure boundaries

Allowed metadata consists of route, success/failure, evidence scope, selected reviewed models, attempt statuses, durations, truncation/synthesis flags and observed token subtotals with coverage. Coverage flags distinguish unknown totals from observed zero; zero-valued partial subtotals do not establish complete usage. Prompts, context, draft/critique/final answers, raw errors, paths, arbitrary model names, billed-cost claims and unknown attributes are excluded.

The exporter owns a private empty-resource tracer provider, filters observations to its generated IDs and fixed names, removes SDK attributes and reconstructs its allowlist. A final export adapter also removes instrumentation-scope credentials, resource attributes, events, links and status descriptions. Only fixed technical scope/type/name metadata is permitted from backend enrichment. No provider credentials or unrelated OTEL exporter settings reach the exporter; Langfuse settings do not reach model workers.

The answer thread writes a small sanitized payload to anonymous temporary input and starts the exporter with hidden/quiet output. SDK startup, network requests and flush run in the child; a daemon reaper attempts termination after 15 seconds while the controller remains alive. A standalone CLI can exit before that reaper runs, so this is not a guaranteed child-lifetime bound. Export is best effort: process shutdown, missing SDK/keys or network failure may drop a trace. Errors cannot replace a valid answer, and no raw exporter logs are forwarded. This is request/stage metadata reporting, not prompt storage or a full billing audit.

References: [Langfuse masking](https://langfuse.com/docs/observability/features/masking), [OTLP endpoint and ingestion version](https://langfuse.com/integrations/native/opentelemetry), [OpenTelemetry exporter interface](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html), [MCP environment configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
