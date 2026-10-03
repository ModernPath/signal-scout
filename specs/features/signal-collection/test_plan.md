# Signal collection — test plan

- Regression: empty/exclusion-only manual requests return HTTP 400 with Monitoring setup guidance and insert no collection job; legacy empty snapshots never contact providers or report complete.
- Regression: all-disabled sources reject a manual run.
- Browser: reload `#collection` and retain the Collection screen; desktop/mobile populated states show actual per-source results and links.
- Live demo: save a labelled demo profile; observe real source URLs in feed, persisted opportunities, company retrieval, refinement, research and a cited editable draft via actual workers. Record source counts and errors separately.

**Behavior:** [Task spec](task_spec.md)  
**Status:** Executed 2026-09-29; see [acceptance results](acceptance_results.md)

| Case | Scenario | Expected result |
|---|---|---|
| C-01 | Advance a controlled clock across a four-hour UTC slot and restart the worker. | One scheduled run is created for the slot, with no bulk replay of old slots. |
| C-02 | Send two manual requests while a run is queued or running. | Both return the same active run and one worker execution occurs. |
| C-03 | Make one fixture adapter succeed and another time out. | The run is partial; successful items persist; the failure appears only on its source row. |
| C-04 | Disable a source or remove its required credential. | It is skipped or unavailable with a clear reason; other sources continue. |
| C-05 | Return malformed fields, an item without a URL, and an AI narrative without cited item URLs. | None creates a source item; rejection counts are recorded. |
| C-06 | Repeat an external source item and use a transient failure fixture. | The item is idempotent and retry budget is respected. |
| C-07 | Inspect run API responses and logs with placeholder credentials. | Credentials, headers, and raw provider payloads are absent. |
| C-08 | With separately configured permitted access, run each adapter once. | A real linked item is recorded or the source reports a provider-specific, actionable status. |

Run C-01 through C-07 with a disposable PostgreSQL database, controlled clock, and adapter fixtures. These cases passed. C-08 is a separate manual smoke check because provider access and external data change; HN, GitHub, X, Web, and a temporarily configured public RSS feed were checked. It remains partially verified because approved Reddit access was unavailable and the local app still has no configured RSS feed.
