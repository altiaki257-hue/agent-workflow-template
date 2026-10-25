# Agent skills

This template includes fourteen task-scoped skills for repository work and answer quality. These are reusable instructions and supporting files, not new model services, permissions, background agents or guaranteed quality improvements. Existing `AGENTS.md`, contracts and client policies remain authoritative.

## Installed catalog

Canonical entrypoints live in `.agents/skills/<name>/SKILL.md`. Each has a small `.claude/skills/<name>/SKILL.md` discovery wrapper pointing to the same implementation. The existing Playwright skills remain unchanged.

| Skill | Source | Use |
| --- | --- | --- |
| `repo-quality` | Custom; requested | Run existing approved checks, inspect complete failure logs and report exact verification. |
| `gh-fix-ci` | OpenAI; requested | Diagnose failing GitHub Actions PR checks and prepare an authorized scoped fix. |
| `task-handoff` | Custom; requested | Populate the existing handoff template from verified Git and test evidence. |
| `gh-address-comments` | OpenAI; requested | Address selected PR review feedback without repeating an already supplied selection. |
| `security-threat-model` | OpenAI; requested | Analyze trust boundaries and concrete abuse paths when threat modeling is requested. |
| `task-contract` | Custom | Scope requested implementation, ownership, criteria and authority using the existing contract template. |
| `repo-navigation` | Custom | Find relevant paths, symbols, callers and tests with bounded retrieval. |
| `regression-debugging` | Custom | Establish a demonstrated cause and a meaningful check for an actual failure. |
| `contract-review` | Custom | Review a specified diff independently, with findings tied to evidence and the contract. |
| `answer-research` | Custom | Research substantive factual questions, reconcile sources and synthesize guarded consultation results. |
| `evaluation-analysis` | Custom | Interpret quality, usage and timing evidence without inventing missing telemetry or general rankings. |
| `security-best-practices` | OpenAI | Perform explicitly requested language-specific security review; load only guides for the actual stack. |
| `screenshot` | OpenAI | Capture a requested native window or region when a more specific capture tool is unavailable. |
| `yeet` | OpenAI, repository-adapted | Publish only an explicitly authorized task, preserving owned-file scope and unrelated work. |

The eight custom skills are short wrappers around maintained repository procedures. The six OpenAI skills retain upstream licenses, relevant helper scripts and resources. Provenance and installed file hashes are recorded in [catalog-lock.json](../.agents/skills/catalog-lock.json).

## Discovery and invocation

Codex loads repository skills from `.agents/skills`; the Claude wrappers resolve to the canonical files and keep their resources relative to that directory. Current OpenCode documentation recognizes both compatibility locations. Either representation leads to the same implementation; this installation does not enable the skill tool or any denied operation inside guarded OpenCode workers.

Examples of explicit invocations include `$repo-quality`, `$task-handoff`, `$answer-research` and `$evaluation-analysis`. Descriptions also support normal task-based discovery. A skill is not a global instruction to run its workflow on every request: read-only questions do not create contracts, ordinary reviews do not trigger threat modeling, and installation never invokes publishing.

Skills become available on the next turn. A running client with a stale discovery cache may need a session refresh. Filesystem and metadata verification do not prove that every installed client version has refreshed or exercised each workflow.

## Upstream source and local adaptations

The reviewed OpenAI catalog has 39 skills at commit `49f948faa9258a0c61caceaf225e179651397431`. Six were selected. The lock records the original and installed hashes of imported files; it also records custom entrypoints, wrappers and additions to imported packages.

Local adaptations:

- All imported entrypoints have concise triggers and explicit repository authority boundaries. Existing task approvals are reused; genuinely missing authority is still required.
- GitHub workflows use current client permissions, rather than prescribing unavailable sandbox escalation. A selected set of comments or an explicit request to address all relevant comments is not asked for again.
- CI fixes remain assigned to the authorized implementer. Live replies, thread resolution, commits, pushes and PR creation require their own task scope.
- Threat modeling requests context only when a material fact is missing; supported analysis can continue while clarification is pending. An optional unanswered question does not become a confirmed assumption.
- Security reviews do not invent a web framework for the current standard-library controller. Generic guidance does not silently authorize implementation or a new report file.
- Screenshot instructions use a short platform router. Windows examples do not bypass execution policy, and the helper's reserved `$home` variable was renamed to `$profileDirectory`. Window rectangles capture visible screen pixels, so visibility and authorized scope must be checked. Python capture loops explicitly require equal ID/output counts to satisfy repository lint and avoid silently dropping captures.
- The publishing entrypoint replaces the upstream stage-everything and pull-on-auth-failure advice with owned-path staging, checks before publishing, explicit authority, and diagnosis of failed remote writes.

The review-comment helper targets the current branch and derives its repository from the PR head. For a different or fork PR, resolve the intended base repository explicitly and use a targeted query. Deduplicate returned item IDs. Its nested review-thread comments are limited to the first 100; do not claim complete coverage when that limit matters.

## Dependencies and data handling

The source installation used an official portable Windows AMD64 GitHub CLI build under `%LOCALAPPDATA%/Programs/GitHub CLI/bin/gh.exe`. The lock records version `v2.103.2` and its release checksum for provenance. No executable, authentication or machine configuration is included here; install and authenticate your own GitHub CLI if needed.

If the current command environment cannot find `gh`, prepend that portable `bin` directory only to the command process PATH before running a bundled helper. The skills explain this fallback. Do not print the full environment, request unnecessary token scopes or alter global client configuration.

New Python packages, model providers, MCP servers, hooks and memory services are not prerequisites for this installation. Existing documentation lookup, OpenAI Docs, Playwright and Obsidian/project-note skills remain available through their current locations. Skill selection grants no permission to expose private data to a provider. Keep raw artifacts outside Git and inspect sensitive output before quoting it.

## Additional catalog decisions

The remaining 33 upstream skills were screened against the current workflow and available tools. Deferred means no installation now, not that the skill is universally unhelpful.

| Group | Deferred skills | Reason |
| --- | --- | --- |
| Application stacks | `aspnet-core`, `winui-app`, `chatgpt-apps` | No corresponding product stack has been selected. |
| Design integrations | The eight `figma` skills | No Figma implementation task or connection is required for this repository workflow. |
| Hosting | `cloudflare-deploy`, `netlify-deploy`, `render-deploy`, `vercel-deploy` | No deployment target is selected; skills do not authorize publishing. |
| Existing capability | `openai-docs`, `playwright` | OpenAI Docs and the existing Playwright CLI skills are already available. |
| Different browser runtime | `playwright-interactive` | Requires a persistent JavaScript runtime not exposed in this session; the existing browser workflow remains. |
| Alternative task systems | `linear`, the four `notion` skills | Existing connections and Git-backed contracts/Obsidian notes cover current needs; no additional service setup or competing source of truth is required. |
| Separate artifact workflows | `pdf`, `jupyter-notebook` | Add when PDF layout or notebook authoring becomes an actual task; ordinary source retrieval and existing evaluation scripts do not need them. |
| Paid/API media workflows | `speech`, `transcribe` | No such task or new API authorization is present. |
| Specialized operations | `sentry`, `security-ownership-map` | No production Sentry analysis or people-to-file ownership topology is needed for the current task. |
| Other setup | `cli-creator`, `define-goal`, `migrate-to-codex`, `hatch-pet` | No new global CLI, background goal, client migration or pet workflow is requested. Task scoping is covered by `task-contract`. |

The existing decision to defer broad orchestration packs and duplicate memory services remains in [agent-efficiency.md](agent-efficiency.md). Skills here add concrete entrypoints rather than changing that architecture.

## Verification and maintenance

Use the skill-creator validator for canonical and wrapper entrypoints. Check wrapper targets and referenced resources, exercise only non-mutating helper modes, then run the repository's required validation and tests. Preserve exact results in the [handoff](../tasks/handoffs/PUBLIC-002-update-to-owner.md).

When updating an imported package, review a pinned revision and its diff, retain its license, reapply intentional local adaptations, refresh hashes and rerun checks. Do not blindly overwrite the repository's authority and privacy constraints with a newer upstream entrypoint.

Rollback consists of removing only these fourteen canonical folders, their fourteen wrappers and the new catalog records. Preserve the existing Playwright skills and unrelated project work. A separately installed GitHub CLI can be removed if no other task needs it.

## Sources

- [OpenAI skill catalog at the reviewed revision](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated)
- [Official OpenAI skill discovery and authoring](https://learn.chatgpt.com/docs/build-skills)
- [OpenCode skill discovery](https://opencode.ai/docs/skills/)
- [GitHub CLI release](https://github.com/cli/cli/releases/tag/v2.103.2)
