# Signal collection — technical spec

Manual collection validates positive monitoring terms and enabled sources before queue insertion; scheduled and initial runs also require these. Legacy queued snapshots without positive terms produce unavailable source rows with a safe setup reason. Live demonstration uses the normal profile and intelligence APIs, real source adapters and workers, not seeded signal records.

Public HN/RSS/GitHub batches commit before model-assisted web/X search, so a slow provider cannot delay their visibility. Grok 4.7 search uses explicit low reasoning effort for discovery, following the [provider's latency-sensitive tool-calling guidance](https://docs.x.ai/developers/model-capabilities/text/reasoning); citation validation and request budgets remain enforced.

**Parent architecture:** [MVP architecture](../../architecture-tech-stack.md)  
**Behavior:** [Task spec](task_spec.md)

## Execution model

The FastAPI process handles `POST /api/collection-runs` by recording a queued run and returning immediately. One worker process polls PostgreSQL, claims a run, executes enabled adapters, and records each source outcome. Scheduled runs use fixed four-hour UTC slots. A unique scheduled-slot value prevents duplicate scheduled runs after a restart; missed old slots are not replayed in bulk.

`collection_run` records trigger, status, timestamps, optional scheduled slot, and a JSONB snapshot of rules and enabled sources. `source_run` records source, status (`complete`, `failed`, `unavailable`, or `skipped`), counts, duration, and a safe error code/message. The snapshot is captured when a run is queued so later profile edits affect only future runs. Manual requests return the existing queued/running run if one exists.

Each source adapter implements the same operation: accept a profile snapshot and budget, then return normalized candidates and counts or raise a classified source error. The worker gives an enabled adapter a budget of 10, retries a transient failure once, and passes its latest published source-item time as an incremental cursor. It commits each source batch independently. On startup, the single worker requeues an interrupted run and skips source rows already committed. A run is complete when all attempted sources succeed, partial when at least one succeeds and another fails or is unavailable, and failed when no attempted source succeeds. Disabled sources are skipped.

## Adapter choices

| Source | Collection method |
|---|---|
| X | xAI X Search, retaining direct public post URLs with matching citation annotations. |
| Web/news | xAI Web Search with citation-backed source URLs and up to two bounded public page fetches; Gemini extraction remains optional and is not enabled in the current adapter. |
| Hacker News | Official recent-item API with local term matching. |
| Reddit | Approved Reddit API access; report unavailable without it. |
| GitHub | Public REST repository and issue search; with a token, bounded GraphQL discussion queries for found repositories. |
| RSS/API | Environment-configured RSS URLs and named adapters only when API credentials and contracts exist. |

The [parent architecture](../../architecture-tech-stack.md#source-adapter-plan) contains provider references and security rules. The xAI Responses adapter reads citation URLs from output-text annotations as well as top-level citations, normalizes equivalent X status URLs by post ID, and rejects uncited generated items. Public page fetching connects to a validated public DNS address with no redirect and keeps the hostname for HTTPS verification. Reject candidates without stable source URLs. Count malformed linked hits as rejected, validate model-produced structured fields before storage, and never treat a model narrative as a source item.

An invalid or out-of-range provider publication timestamp is treated as unavailable time for that item. It must not fail the source run.

## API and UI

`GET /api/collection-runs` returns recent runs with source rows; `POST /api/collection-runs` queues or returns the active run. The Collection screen polls the active run at a modest interval and displays partial or unavailable status without claiming stale items are fresh.
