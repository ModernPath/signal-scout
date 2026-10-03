# Signal collection — task spec

**Parent scope:** [Phase 1 MVP PRD](../../phase-1-prd.md)  
**Related design:** [Collection screen](../../design/index.html)

## Outcome

The operator can start or await a collection run, see when each source was checked, and understand partial results without losing successful signals.

## In scope

- Run collection after the first monitoring save, every four hours, and on manual request.
- Search enabled sources: X, Web/news, Hacker News, Reddit, GitHub, and configured RSS/selected APIs where permitted access exists.
- Normalize accepted source items with a stable URL, title, snippet, publication time when available, source, engagement metric, and matched terms.
- Show queued, running, complete, partial, or failed run status and per-source counts or safe errors.
- Keep successful source results when another source fails. Previously collected items remain visible with their original timestamps.
- Bound query volume, retries, and provider costs for each run.

## Boundaries

This feature does not do real-time streaming, ask the user for API keys in the UI, scrape around denied API access, or guarantee a source that lacks required credentials. Feed presentation and deduplication belong to the [Feed feature](../signal-feed-triage/task_spec.md).

## Acceptance criteria

1. The four-hour schedule creates one run per slot. An active run is reused when manual refresh is requested again.
2. Every enabled source with permitted access can return normalized source items or an actionable source status.
3. A missing credential or provider outage affects only that source, with a partial run when another source succeeds.
4. An item lacking a stable source URL is rejected, and no AI-generated answer alone becomes a signal.
5. Run history exposes trigger, start/end time, source counts, and errors without exposing credentials.
6. Collection requires at least one topic, include keyword, competitor, or person and an enabled source. Empty or exclusion-only profiles receive an actionable setup error rather than a successful zero-request run. Previously queued empty profiles report missing monitoring terms without contacting providers.

## Live demo acceptance — 2026-10-02

Configure the currently empty local workspace with explicitly labelled SignalScout demo company context and AI/agent monitoring. Collect real linked public items through available sources, analyze them into opportunities, retrieve company passages, refine one angle, research it and generate an editable cited draft through the application's worker. Report individual source outcomes; unavailable Reddit access is not bypassed and demonstration company claims are labelled as examples.
