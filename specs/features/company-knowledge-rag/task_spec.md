# Company knowledge RAG — task specification

**Status:** Implemented; technical verification recorded in [acceptance results](acceptance_results.md). Representative company editorial acceptance remains pending.
**Product:** [Phase 2 PRD](../../phase-2-prd.md).

## Outcome

Give the intelligence agent relevant company passages and checked research evidence when assessing opportunities and drafting. The operator can inspect what was retrieved, see where an argument repeats previous content, and review a specific alternative angle with citations. PostgreSQL remains the source of truth for application and agent memory.

## Current gaps

`intelligence_core.py` compares whole previous articles with token overlap. A paraphrased claim or a relevant section buried inside a long article can be missed. The current draft provider receives a bounded research list and company brief, without retrieval of previous company passages. The main analysis queue deliberately runs deterministic analysis without a provider. RAG adds retrieval to these shared use cases; it does not establish that a retrieved claim is true.

## Delivery sequence

| Slice | Operator outcome | Scope |
|---|---|---|
| 1. Company retrieval | Saved content gets an indexing status; opportunity detail shows relevant previous passages | Postgres vector extension, incremental indexing, retrieval inspection, lexical fallback, main UI |
| 2. Fresh angles | See what was previously argued, what overlaps, and an evidence-supported alternative | Claim comparison, cited Why us/angle enrichment, explicit coverage and confidence |
| 3. Research and drafts | Drafts use selected research evidence and appropriate company context | Evidence indexing, immutable retrieval records, separate factual and voice citations |
| Later: signal matching | Find related signals that use different words | Separate clustering experiment and feature contract after slices 1–3 pass; retain entity/time safeguards |

All first three slices form this feature. Semantic clustering is subsequent scope, because retrieval similarity alone is insufficient to merge stories.

## User flows and UI

1. Save or edit previous content in **Company context**. Continue using text/title/channel and an optional source URL; a URL is a reference, not an automatic fetch. See Pending, Ready, or Failed indexing status, progress, and Retry. A compact knowledge status shows indexed versus eligible content and last successful update.
2. Run **Analyze** in Opportunities. Review the existing deterministic scores plus previous-content passages with title, excerpt, channel, and source link where supplied. See whether the comparison used semantic or lexical retrieval and whether coverage was incomplete.
3. Request **Refine angle** on a selected opportunity. See the prior claim, overlap, suggested difference, citations, and uncertainties. A subject match alone is not labeled a repeated claim. Keep generated enrichment separate from numeric ranking.
4. Research the selected opportunity through the existing action. Inspect supporting, conflicting, and unknown evidence. Retrieval from stored research helps synthesis; fresh web research still uses the existing grounded provider.
5. Generate an editable LinkedIn/X post or reply. Inspect **Factual sources** separately from **Company context used**. Prior posts guide voice and editorial continuity; they are not independent corroboration of public claims.
6. Delete company content. It immediately stops being eligible for retrieval; derived passages and embeddings are purged, historical retrieval excerpts are redacted, and affected outputs show that a source was removed. Existing generated drafts remain operator-owned text with a clear source-removal warning.

Use the existing shell, context form, opportunity detail pane, queue status, live regions, and responsive layout. Before UI implementation, add a feature prototype here and review it against the shared design.

## Acceptance criteria

- **AC1:** Content added/edited through the main app or standalone service becomes indexable without copying it into another database; unchanged content incurs no repeated document embedding calls.
- **AC2:** Retrieval finds a relevant passage expressed with different words, alongside exact product/entity matches. Results show original excerpts and real source/version IDs.
- **AC3:** A repeated claim is distinguished from a different claim about the same topic. No matches or missing coverage never imply proven novelty.
- **AC4:** Refinement explains Why us and the angle using company context and opportunity evidence; factual statements have supplied evidence citations or are explicitly uncertain.
- **AC5:** Research/drafting preserve the complete-research and company-brief requirements. Unsupported IDs are rejected; company voice passages cannot satisfy the factual-evidence requirement.
- **AC6:** Edits invalidate the old version immediately; deletions/retention expiry exclude and purge derived content. Concurrent stale jobs cannot republish it.
- **AC7:** Missing credentials, partial indexing, quota errors, or empty retrieval are visible. Inspection and deterministic analysis remain available; lexical comparisons are labeled, and insufficient research continues to block drafting.
- **AC8:** Slow embedding/generation uses the existing worker queue. Both main UI and independent agent interfaces share the retrieval service, storage, and validation contracts.
- **AC9:** Each generated enrichment/draft records the versions and passages used. Changes to corpus, retrieval configuration, or models invalidate applicable cached results.

## Boundaries and inputs

Initial ingestion is existing operator-pasted text and stored evidence; PDF/DOCX uploads, automatic crawling, chat-history indexing, managed remote stores, automatic publishing, and hosted multi-user access are deferred. A general knowledge chat screen is also deferred; retrieval inspection exists to support opportunity work.

Representative company content and editorial judgments are needed for final acceptance. Start offline with synthetic fixtures; use a bounded opt-in Gemini smoke test after implementation. Embedding private company text sends it to the configured provider, so the UI must explain that processing when semantic indexing is enabled.
