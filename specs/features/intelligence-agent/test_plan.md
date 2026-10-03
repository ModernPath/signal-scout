# Standalone intelligence agent — test plan

**Behavior:** [Task spec](task_spec.md)  
**Status:** Implemented and partially accepted 2026-10-01; see [acceptance results](acceptance_results.md)

| Case | Scenario | Expected result |
|---|---|---|
| I-01 | Two related cross-source signals, one unrelated signal, and a repeated source item. | Two conversations; no lost or duplicated provenance; rerun with unchanged inputs returns the same analysis version. |
| I-02 | Broad shared monitoring topic but different named events, plus ambiguous same-title signals. | Distinct conversations; uncertain pair stays separate and match reasons are inspectable. |
| I-03 | Controlled timestamps with a recent rise, steady activity, and too little history. | Velocity ordering reflects distinct arrival rates; insufficient history says unknown and lowers confidence. |
| I-04 | Change only source-specific engagement units and values. | Opportunity ranking does not gain an artificial cross-source popularity boost. |
| I-05 | Import a prior article with the same claim, then one with a related topic but different claim. | Similarity is cited and lowers novelty; a supportable new angle survives. Missing library yields unknown novelty. |
| I-06 | Omit the company brief, then supply a complete brief with documented expertise and constraints. | Company fit and Why us are unavailable first; later rationale references brief evidence and avoids prohibited claims. |
| I-07 | Research adapter returns two supporting URLs, one contradictory URL, and one timeout. | Dated evidence includes direct URLs, conflict, and partial failure; synthesis does not claim consensus. |
| I-08 | Model returns fabricated source IDs/URLs or instructions embedded in a source page. | Invalid citations and source instructions are rejected; no fabricated evidence is persisted. |
| I-09 | Request each draft type for a researched selection, then request one without adequate evidence. | Four editable, versioned drafts with valid evidence references; insufficient case reports why it cannot draft; no publish call occurs. |
| I-10 | Run with no provider key and with a provider error. | Offline analysis/inspection work; research/drafting return an explicit unavailable or partial state and leave existing records intact. |
| I-11 | Run migrations twice and invoke CLI against disposable PostgreSQL with web stopped. | Schema is repeatable, CLI works independently, and Phase 1 records/flags are unchanged. |
| I-12 | Inspect logs, CLI errors, and stored rows with placeholder keys/private text. | No secrets or raw provider payloads leak; retained private content matches the documented data policy. |
| I-13 | Add, replace, list, and delete company brief/content through chat, direct tool, API, and agent UI. | Every surface sees the same PostgreSQL state/version; deleting context does not corrupt historical analysis provenance. |
| I-14 | Invoke each of the three subagents with valid IDs, malformed JSON, missing rows, timeout, and provider error. | Validated JSON envelopes and bounded exits; service persists only valid results and reports partial/failure safely. |
| I-15 | Ask equivalent analysis and inspection questions in model chat and offline chat; exceed history/tool budgets. | Both call the same service data, history is bounded, tools stop at budget, and offline mode never invents research/drafts. |
| I-16 | Exercise direct tool CLIs and local FastAPI routes for analysis, research, drafts, and chat. | IDs, scores, citations, errors, and versions agree across surfaces; cross-origin mutations and malformed payloads are rejected. |
| I-17 | Run the independent agent UI at desktop and narrow widths in a real browser. | Main journey, empty/loading/partial-error states, keyboard focus, and readable evidence/drafts work; screenshots are saved outside the repository. |
| I-18 | Persist chat and research excerpts, advance a controlled clock past retention, and invoke cleanup. | PostgreSQL chat/excerpt records expire as documented while citation metadata and selected drafts remain; operator deletion removes allowed private context. |

Use a disposable PostgreSQL database and fixed clocks for I-01 through I-06 and I-09 through I-18. Fake provider boundaries for I-07, I-08, I-14, and model chat in I-15. Run I-17 in a real browser against the independent agent UI, comparing its own approved feature design once created; the Phase 1 SignalScout prototype is not the agent UI baseline. After these pass, run a separately authorized live provider check and human editorial review on representative company material; record costs, failures, incorrect merges, misleading scores, and unsupported draft claims. This plan does not claim acceptance until those observations and the independent-agent feature review are recorded.
