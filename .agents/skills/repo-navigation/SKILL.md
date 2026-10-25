---
name: repo-navigation
description: Locate implementation, configuration and tests with bounded searches and symbol references. Use for repository fact-finding before broader file reads.
---

# Repository navigation

Resolve the current checkout and the precise fact or decision the user needs. Follow the [targeted retrieval boundary](../../../docs/architecture.md#targeted-retrieval) and applicable contract; do not read archives or unrelated worktrees as routine context.

- Start with likely paths, `rg --files` globs, then a specific identifier or behavior in those paths. Use Serena symbol overviews or references when available and more direct than text search.
- Inspect caller, definition and the relevant test or configuration only as needed to establish the behavior. Read bounded line windows around matches before opening a large file.
- Batch independent searches and reads; keep edits, dependencies and adaptive follow-ups sequential. Set useful output limits, and inspect every result, including errors and truncation.
- If results are too broad, narrow the query or directory and continue from a saved full result when needed. Do not treat a truncated search or absent match as proof of absence.
- Respect Git ignores and excluded generated files, dependencies, caches, secrets and unrelated worktrees. Do not dump environment variables or effective configuration to discover a single setting.

Return the answer with the few paths, symbols and relevant line numbers that establish it. Distinguish observed runtime facts, documented intent and inference. Broaden retrieval only when the bounded search cannot answer the question; do not add a repository-wide scan or team call to an already evidenced answer.
