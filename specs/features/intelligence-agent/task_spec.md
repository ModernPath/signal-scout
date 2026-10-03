# Standalone intelligence agent — task spec

**Parent scope:** [Phase 2 PRD](../../phase-2-prd.md)  
**Technical design:** [Technical spec](technical_spec.md)  
**Status:** Independent agent implemented; acceptance gaps are in [results](acceptance_results.md)

## Outcome

One trusted local operator can use a complete, independent `agents/signal-intelligence/` agent against the application's PostgreSQL database to discover, inspect, research, and draft from content opportunities before any **SignalScout application** UI work begins.

## In scope

- Store an explicit company brief and previous content records, with stable IDs, source URLs where available, timestamps, and provenance. Support adding, listing, and replacing those records through the CLI.
- Read a bounded recent signal window; honor Phase 1 dismissed state for default analysis and retain the source items behind each included signal.
- Cluster related signals into conversations, assign a concise topic label, retain member IDs and reasons, and avoid merging solely because signals share a broad monitoring topic.
- Rank conversations using relevance, velocity, novelty against previous company content, and company POV fit. Show component values, overall score, confidence, and the evidence behind each component. Do not equate source-specific engagement metrics.
- Produce Why now, Why us, and angle explanations with citations to stored source items and company context. If the brief is absent, mark company fit and Why us as unavailable.
- Research a selected opportunity through bounded, permitted retrieval. Summarize supporting and contradictory evidence, freshness, gaps, and source URLs. An unavailable provider or failed fetch yields an explicit incomplete result.
- Generate editable LinkedIn and X post drafts and reply drafts from a selected researched opportunity. Tie each draft to an evidence snapshot, channel, and version; require operator selection and adequate evidence.
- Provide the same service actions through a conversational CLI, direct JSON tool CLIs, a local agent API, and a local agent UI with chat and direct controls. Conversation history is bounded and persisted in PostgreSQL.
- Give the agent domain-specific skill instructions and narrow subagents for topic analysis, evidence research, and draft writing. The chat model uses documented service tools; an offline command router uses those same service actions. Subagents exchange bounded JSON envelopes with the service.
- Keep all writes and agent memory in application PostgreSQL and all network/model use behind explicit operator actions and budgets.

## Boundaries

No **SignalScout application** UI/API changes, publishing, scheduling, authentication for remote users, scraping around provider restrictions, or generation of new Phase 1 feed signals from model text. The independent agent's API and UI are reachable only through localhost host ports. The agent has no local JSON memory store. The application owns migrations, and the agent must not alter Phase 1 source records or triage flags.

## Acceptance criteria

1. With two related signals and one unrelated signal, analysis creates two conversations, retains all original signal/source-item IDs and links, and is idempotent for the same input version.
2. Ranking displays four separately computed components, an overall score, and confidence. A newer multi-source conversation can have higher velocity; missing history is shown as unknown rather than zero. Source-specific metric units do not become a cross-source popularity score.
3. A similar prior content item lowers novelty and is cited. A different, supportable angle remains possible. Missing prior content is described as unknown novelty.
4. Why now, Why us, and angle explanations cite stored signal evidence and company context, and explicitly identify missing support.
5. Research on a selected opportunity saves a bounded, dated evidence record with direct URLs, support/conflict labels, and fetch/provider failures; no uncited factual claim is promoted as verified.
6. Drafting requires a selected, researched opportunity and a complete company brief. It creates separate LinkedIn post, X post, LinkedIn reply, and X reply drafts, with evidence and version references. Draft text is not posted.
7. With an unavailable model or research provider, offline inspection and deterministic analysis still work; research/drafting report a clear unavailable state without fabricated results.
8. All new persisted records live in the application's PostgreSQL database; migrations are repeatable, tests use disposable data, and the standalone process does not require the SignalScout web service.
9. Chat, direct tools, local API, and local agent UI call the same service use cases and return consistent opportunity, research, draft, and error states. Offline chat routes supported commands without fabricating unavailable research or drafts.
10. The three subagents have one documented job each, bounded inputs/timeouts, validated JSON stdout, and no independent publishing or Phase 1 mutation permission. Their failures leave stored work consistent and visible.
11. Agent memory persists company context, prior content, analysis, research, drafts, and bounded chat sessions in PostgreSQL. The operator can inspect and delete permitted private context; retention is documented and tested.
12. The agent UI supports the main workflow at desktop and narrow widths, including loading, empty, partial-error, and keyboard states, while remaining separate from the SignalScout application UI.
