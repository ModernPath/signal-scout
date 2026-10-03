# Signal feed and triage — test plan

**Behavior:** [Task spec](task_spec.md)  
**Status:** Executed 2026-09-29; see [acceptance results](acceptance_results.md)

| Case | Scenario | Expected result |
|---|---|---|
| F-01 | Ingest two items with the same canonical URL and repeat one external ID. | One signal appears with two contributors; the repeated ID is idempotent. |
| F-02 | Ingest similar titles with different target hosts or times outside the matching window. | They remain separate signals. |
| F-03 | Combine source, topic, date, engagement, and state filters over several pages. | Results are correct, bounded, and newest first. Source matches any contributor; engagement uses the primary item. |
| F-04 | Save, mark interesting, dismiss, restore, and reload a signal. | Flags persist independently and each state view includes the correct items. |
| F-05 | Open detail on a grouped signal. | Matched terms, metrics, all source items, and original links appear. |
| F-06 | View the feed twice with new items inserted between visits. | “New since last visit” uses the prior review marker and remains stable while the current visit is displayed. |
| F-07 | Ingest HTML/script text and unsafe URLs in source fields. | Text is escaped and unsafe links are not opened. |
| F-08 | Review desktop/mobile, empty, and partial-data states. | Navigation, filters, triage, and status remain readable and usable. |

Use the real API with a disposable PostgreSQL database and fixed source-item fixtures for F-01 through F-07. These cases passed. F-08 was exercised at desktop and 390 px mobile widths, including empty and partial-data states. Direct visual comparison to the approved prototype remains unverified because the browser rejected its local file URL. Fixtures covered different engagement units, duplicate URLs, missing timestamps, and malicious text.
