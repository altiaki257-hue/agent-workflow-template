---
description: Research and independently critique a question before answering
agent: answer-coordinator
---

Call answer_team_ask_team once with mode consult and the question below. Its controller enforces researcher then independent critic. Synthesize their separate draft/critique into a single grounded final answer; address supported corrections rather than forwarding the draft. Do not use native task delegation, edit, run shell commands, or claim review if the tool fails.

For MCP 2.x, follow structuredContent.answer_location to content[0].text for the labelled draft and critique; do not read the removed structuredContent.answer/draft/critique fields. Retain synthesis_required, provenance, artifact_coverage and truncation metadata. Distinguish partial critic coverage from omitted delivery: additional draft text may be unreviewed. A true synthesis_required value or the text's provisional-draft notice requires your own synthesis before answering. Treat the location only as a response field reference.

Question: $ARGUMENTS
