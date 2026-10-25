---
name: answer-research
description: Research substantive factual questions and recommendations with bounded primary-source evidence. Use when freshness, uncertainty or conflicting sources materially affects the answer.
---

# Evidence-led answers

Identify the decision or factual question, its scope and what evidence would change the answer. Answer simple, sufficiently evidenced questions directly. A recommendation is advice unless the user requests implementation; do not turn research into edits or external actions.

Use relevant connected sources for user-specific meaning and targeted repository reads for local facts. For library, API and CLI details, use the available documentation lookup skill and current documentation as required by `AGENTS.md`. For OpenAI products, use OpenAI Docs and official sources. For changing external facts, search current primary sources and actually read the supporting page or paper.

Keep queries specific and non-sensitive. Compare versions, publication and event dates, conditions and scope before combining claims. Search snippets locate evidence; model agreement, rankings and promotional claims do not establish facts. Resolve conflicting evidence at its source and label material inference or missing measurements.

Use the existing [answer pipeline](../../../docs/answer-pipeline.md) when repository policy calls for consultation. Supply only bounded approved evidence, choose `supplied` for a self-contained case, and use `repository` only for missing repository facts. Never send credentials, private code, personal data or whole chats to an unapproved provider. Synthesize both provisional draft and distinct critique; verify their claims independently, disclose failures or truncation, and do not repeat the consultation without new evidence or changed scope.

Lead with the answer and connect evidence to the user's decision. Put citations next to the claims they support; use local file links for repository facts and direct primary-source links for external facts. Distinguish available, installed, authenticated, tested, reviewed and integrated states. Avoid invented precision, unmeasured efficiency claims, unsupported compatibility promises and broad warnings unrelated to the task.

Keep the final answer as short as the decision permits. If missing information materially changes the outcome, ask one focused question while continuing independent useful work; do not repeatedly ask about a preference the user has already supplied or treat silence as approval.
