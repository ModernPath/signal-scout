# SignalScout — Phase 1 MVP PRD

**Product:** SignalScout  
**Status:** Scope agreed from the [UI prototype](design/index.html)  
**Last updated:** 2026-09-29

## Summary

SignalScout helps a content or communications lead find timely conversations for thought leadership. The MVP lets one operator configure what to watch, collect signals from several sources, and review one deduplicated feed. The operator can filter signals and save, dismiss, or mark them interesting. It does not generate or publish content.

The MVP has three screens: **Signal feed**, **Monitoring**, and **Collection**. The [architecture specification](architecture-tech-stack.md) describes the product-wide implementation. Smaller feature specifications are listed in the [feature index](features/README.md).

## Product decisions for this MVP

| Decision | MVP choice |
|---|---|
| Operator and deployment | One default workspace and one trusted operator, run locally. No sign-in or team management. |
| Collection cadence | Every four hours, plus manual refresh. Saving the first monitoring profile queues an initial run. |
| Feed order | Newest published signal first. |
| Engagement threshold | One optional numeric feed filter. Each card displays its source's unit (likes, points, stars, etc.); no cross-source score or collection-time cutoff. |
| Interesting signals | Mark and filter in the UI. Export is deferred. |
| Trends | Trend, velocity, and acceleration calculations and screens are deferred. |

## Problem and users

Signals are scattered across X, news, forums, code communities, and feeds. Manual review is slow, and the same story often appears in several places.

- **Primary user:** A content or communications lead who owns monitoring and follow-up.
- **Secondary user:** A founder or subject-matter expert using the same single-operator workflow.

## MVP goals

| Goal | Expected outcome |
|---|---|
| Configurable monitoring | Topics, include/exclude keywords, competitors, people, and source toggles guide collection. |
| Unified feed | One chronological list with source provenance and duplicate hits grouped. |
| Useful triage | Save, dismiss, and mark interesting actions persist between sessions. |
| Visible collection health | The operator sees the last run, per-source status, and partial failures. |

## Product scope

### Monitoring

- Add and remove topics, include keywords, exclude keywords, competitors, and influential people. Changing an entry can be done by removing and adding it again; a separate edit dialog is not required.
- Competitors may use a name, domain, or handle. People may use a name, handle, or profile URL.
- Enable or disable each supported source. The saved profile persists in PostgreSQL.
- Keep API credentials outside the UI and database. Missing credentials appear as an unavailable source in Collection.

### Collection

| Source | MVP collection expectation |
|---|---|
| X | Recent public posts matching configured topics and tracked entities through a permitted search integration. |
| Web / news | Current pages and articles discovered by web search; fetch and extract enough text for a useful signal. |
| Hacker News | Recent stories and comments checked against configured terms. |
| Reddit | Posts and comments found by search for configured terms, subject to approved API access. No subreddit picker is required. |
| GitHub | Relevant public repositories, issues, and discussions where the selected API supports them. |
| RSS / selected APIs | Items from feeds configured in the environment and selected APIs with available credentials. |

- A scheduled run starts every four hours. The operator can request a manual run. An already queued or running collection is reused rather than duplicated.
- A run records start/end time, trigger, status, and per-source counts and errors. A source failure makes the run **partial**, while successful sources still update the feed.
- A failed provider may leave its last successfully collected results visible. The UI must label the source failure and must not imply those results are fresh.
- Store title, snippet, URL, source, published time, source-specific engagement, matched topics, and provenance for each accepted result. Discard items without a stable source URL.
- Apply practical query budgets, rate limits, and incremental fetches to control provider cost.

### Signal feed and detail

- Show one chronological feed of deduplicated signals, with contributing sources available in detail.
- Group repeated hits by canonical content URL first; use normalized titles and a short time window for conservative cross-source matching. Keep underlying source items so provenance is not lost.
- Filter by source, topic, date range, and minimum engagement. The engagement threshold applies to the displayed primary metric of each source and does not imply comparable popularity across sources.
- Detail shows the full available snippet, why the signal matched, source metrics, contributing sources, and a link to the original item.
- **Save:** bookmark for later. **Dismiss:** hide from the default feed but retain in a Dismissed view. **Interesting:** mark as a positive follow-up signal. These flags can coexist and can be reversed.
- Include All, Saved, Interesting, and Dismissed views. The default All view excludes dismissed signals.

## Core user flows

1. **Set up monitoring:** Add topics and terms, optionally add competitors and people, select sources, and save. The first run is queued.
2. **Collect:** Wait for the four-hour schedule or select manual refresh. See running, complete, partial, or failed status by source.
3. **Review:** Filter the feed, open a signal, follow its original link, and save, dismiss, or mark it interesting.
4. **Return later:** See new signals since the last review and revisit Saved, Interesting, or Dismissed items.

## AI-assisted search

| Capability | Environment variable | MVP use |
|---|---|---|
| Web and X discovery | `XAIGROK_API_KEY` | xAI web and X search tools discover recent source items and URLs. |
| Page understanding | `GEMINI_API_KEY` | Optional extraction or relevance check for ambiguous web results; output must be validated before storage. |

Credentials load from `.env` at runtime and are never committed. If either provider is unavailable, the affected source reports an error and other sources continue. Query expansion and relevance checks are bounded by per-run budgets. Generated text is never accepted as a signal without a verifiable source URL.

## Functional acceptance criteria

- [x] Monitoring entries and source toggles can be changed and survive a restart.
- [x] An initial, scheduled, and manual collection can be observed in the Collection screen.
- [ ] Each enabled source with configured, permitted access can contribute normalized signals; unavailable sources show a clear reason.
- [x] Repeated source items do not create repeated feed cards, and grouped items retain provenance.
- [x] Source, topic, date, and engagement filters work together.
- [x] Save, dismiss, and interesting actions persist and can be reversed.
- [x] A partial run retains successful results and reports the failing source.
- [ ] No API key appears in the browser, logs, or committed files.

## Conceptual data

- **Monitoring profile and rules:** The single workspace's topics, terms, competitors, people, and enabled sources.
- **Collection run and source run:** Trigger, status, timestamps, counts, and safe error summaries.
- **Source item:** A normalized result from one external source, including URL, source ID, time, metric, and matched rules.
- **Signal:** The deduplicated feed item linked to one or more source items.
- **Signal state:** Saved, dismissed, and interesting flags with timestamps for the default operator.

## Success measures

- First useful feed within 15 minutes of saving the initial profile, assuming at least one source is configured and available.
- Qualitative beta feedback on the share of saved or interesting signals the operator would not have found manually.
- Duplicate hits grouped per 100 raw hits, with manual review of mistaken merges.
- Per-source collection success rate and p95 run duration.

## Risks and handling

| Risk | Handling |
|---|---|
| Provider access, limits, or terms change | Keep a separate adapter per source, use only permitted access, and show unavailable/partial status. |
| Search cost | Four-hour batches, query budgets, caching, and incremental fetches. |
| Noisy results | Include/exclude rules and an optional bounded Gemini relevance check. |
| Mistaken duplicate grouping | Conservative matching and retained source items. |
| Stale results after a failure | Keep last good items but surface the source's latest failure and run time. |

## Deferred scope

Trends and acceleration; exports and webhooks; content briefs, drafting, and publishing; outreach and CRM; team workflows and alerts; hosted multi-user access, SSO, billing, and advanced roles; sub-second streaming.
