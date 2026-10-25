# Agent workflow template

A reusable foundation for an Emdash, Claude Code, Codex and OpenCode workflow. Includes scoped task contracts, read-only research/critique tooling, policy checks, tests, optional Obsidian archiving and opt-in Remotely Save dispatch.

The archive supports stable chronological filenames and migration that preserves annotations. Fourteen additional [agent skills](docs/agent-skills.md) cover navigation, debugging, checks, research, reviews and explicitly authorized publishing.

This is a sanitized source snapshot, with no original Git history, remotes, personal task records, chat archive, credentials or machine configuration. Nothing is connected or pre-authorized on a new machine. See [public-copy audit](PUBLIC-AUDIT.md).

## Setup

1. Install Git, Python 3.11+ and your chosen agent clients.
2. Run `python -m pip install -r requirements-dev.txt`.
3. Read [AGENTS.md](AGENTS.md) and [workflow](docs/workflow.md), then configure your own accounts outside Git. Verify current model availability and account costs before inference; no paid use is pre-approved.
4. Replace the example GitHub repository URL in `scripts/configure_notes.py` with your public repository URL before generating source links.
5. Run `python scripts/validate_repo.py` and `python -m unittest discover -s tests -v`.

Obsidian archive/sync, observability, browser and account integrations are optional and require separate local setup. Templates and examples do not establish that a service works on your machine. This template was sanitized before publication and imports no private repository history. Choose your own public commit identity and a license before describing a derived project as licensed open-source software.
