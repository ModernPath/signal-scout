# Intelligence UI — test plan

Use disposable PostgreSQL with fake provider boundaries for TDD, never real company records.

| Case | Verification |
|---|---|
| U-01 | Main API brief and content round trips, replace/delete, validation, restart persistence; browser forms add/edit/delete. |
| U-02 | Queue analyze without a key; worker builds ranked opportunities from Phase 1 fixtures, retains triage, provenance, missing components; detail/unknown ID; browser list and reasons. |
| U-03 | Fake research includes support/conflict and partial/error; terminal job and evidence detail agree; browser progress and safe error display. Separately run one bounded live Gemini check with public sources. |
| U-04 | Four channel/format jobs invoke shared service; missing brief/research/provider rejected; unsupported evidence/length rejected; edit creates new version preserving original and source snapshot; escaped rendering and copy behavior. |
| U-05 | Duplicate and concurrent/conflicting submissions, reload/status, claim and stale/restart recovery, no automatic replay, exception redaction; job results contain IDs only. |
| U-06 | Cross-origin requests, malicious links/text, invalid IDs/enums/limits, original application regression suite; localhost Compose and credential boundary inspection. |
| U-07 | Actual browser at desktop/narrow against shared prototype and feature prototype; main flow, empty/busy/partial/error, keyboard/focus, overflow; temporary screenshots and acceptance results. |

Exit: relevant suites green, deployed local services healthy, guided journey observed, material review findings fixed; distinguish live public fixture verification from actual company editorial acceptance.

See [acceptance results](acceptance_results.md) for commands, browser evidence, and explicit unverified comparison cases. Automated API tests enforce the disposable `signalscout_ui_test` database name; live browser checks use a separate `signalscout_ui_browser_test`.
