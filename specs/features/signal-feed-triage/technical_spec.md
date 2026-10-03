# Signal feed and triage — technical spec

**Parent architecture:** [MVP architecture](../../architecture-tech-stack.md)  
**Behavior:** [Task spec](task_spec.md)

## Storage and deduplication

`source_item` has a unique `(source_key, external_id)` key and a foreign key to `signal`. For sources without an external ID, derive one from the source URL hash. `signal` stores the grouped title, snippet, canonical URL key, and displayed publication time. `signal_topic` stores matched topic text rather than a mutable profile-rule ID so historical topic filters continue to work after profile replacement. The singleton operator's `signal_state` stores saved, dismissed, and interesting flags with timestamps.

On ingest, first check the unique source-item identity and return its existing signal when repeated. Remove known tracking parameters from its content URL. Match by canonical URL key; otherwise use normalized title, same target host, and a 48-hour publication-time window. Do not merge ambiguous items. Keep the original source URLs and items after grouping. The most recently published linked item supplies the displayed time and primary engagement metric; an equal-time item with a metric wins over one without a metric.

## API and UI

- `GET /api/signals`: bounded pagination, newest first, optional source/topic/date/minimum-engagement/state filters. A source filter matches any linked source item; engagement checks only the displayed primary metric.
- `GET /api/signals/{id}`: grouped detail, matched terms, contributing items, and original URLs.
- `PATCH /api/signals/{id}/state`: set the three independent booleans and timestamps without changing the other flags.
- `GET /api/summary`: counts for the feed header. `POST /api/feed-reviewed` records the review marker after the current page has loaded. Capture the previous marker first so “new since last visit” stays stable during that visit. Returning to the feed refreshes found/duplicate counts while preserving that visit's new count.

Use the approved [HTML/CSS/JavaScript prototype](../../design/index.html) as the visual baseline, building the running feed UI with same-origin API calls and no mock arrays. Escape all external text. Validate URL schemes and use `rel="noopener noreferrer"` for links opened in a new tab. Exclude dismissed items only from the default All state, not from Saved or Interesting when explicitly selected. Keep keyboard focus inside the open detail dialog and return it to the invoking control on close. Serve a content-versioned client script with `no-store` response headers so deployments do not leave an older API client cached.
