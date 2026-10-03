# Signal feed and triage acceptance — 2026-09-29

Environment: real API with fixed source fixtures in disposable PostgreSQL, plus Chrome browser against an isolated local app. The browser was checked at desktop and 390 × 844; measured mobile document width equaled the 390 px viewport.

| Case | Result | Evidence |
|---|---|---|
| F-01 | Pass | Canonical tracking variants grouped; repeated external ID stayed idempotent. Browser showed one grouped card with two contributors and one duplicate hit. |
| F-02 | Pass | Different target hosts and publication times outside 48 hours remained separate in `test_conservative_title_grouping_and_safe_urls`. |
| F-03 | Pass | Composed API filters, bounded paging, newest order, contributor-source and primary-metric rules passed. Browser source + topic + date + engagement filters showed the expected grouped GitHub card. With 23 fixtures, the browser showed 20 cards on page 1 and the remaining 3 on page 2 in newest-first order. |
| F-04 | Pass | Browser saved, marked interesting, dismissed, restored, and reloaded one signal. Saved and Interesting retained the dismissed signal; All excluded it. The browser also reversed Save and Interesting independently, and their views became empty. API persistence test passed. |
| F-05 | Pass | Browser detail showed both contributing source items, matched terms, different metric units, and original links with `_blank` and `noopener noreferrer`. |
| F-06 | Pass | Review-marker API test covered two visits. Browser showed two new signals on the first post-ingest visit and zero on the next. After 21 further items arrived, the next visit showed 21 new; one more item inserted during that visit raised Found from 23 to 24 on returning to the feed while New stayed 21. |
| F-07 | Pass | A title containing literal `<img ... onerror=...>` rendered as text in desktop/mobile browser. Unsafe URL ingestion was rejected in tests; original links used safe attributes. |
| F-08 | Not verified in full | Desktop/mobile populated feed, partial collection health, and empty filtered state were usable, with no mobile horizontal overflow. The browser rejected the approved prototype's local file URL, so direct visual comparison and its screenshot were unavailable. |

Screenshots: `/private/tmp/signalscout-acceptance-20260929/feed-desktop.png`, `/private/tmp/signalscout-acceptance-20260929/feed-mobile-full.png`, `/private/tmp/signalscout-acceptance-20260929/feed-empty-filter-desktop.png`, and `/private/tmp/signalscout-acceptance-20260929/feed-pagination-page2.png`. Focused rendering tests caught and then verified singular signal, hit, and engagement-unit labels. Versioned, `no-store` JavaScript responses were added after the browser retained a stale client script. Detail-dialog keyboard focus wrapped from its last link back to the close button, and closing after an 8-second feed poll restored focus to the current card's Details button.
