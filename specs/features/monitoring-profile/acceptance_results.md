# Monitoring profile acceptance — 2026-09-29

Environment: isolated PostgreSQL `feature_accept`, local web app on port 8001, Chrome at desktop and 390 px widths. Automated persistence tests used a separate disposable `featuretest` database. No provider credentials were entered in the browser.

| Case | Result | Evidence |
|---|---|---|
| M-01 | Pass | Entered all five rule kinds, changed three of six toggles, saved, reloaded, and restarted the web process. Values and the three selected sources persisted. The worker entry point restarted successfully with `--check` against the same database. `test_profile_round_trip_and_initial_run_snapshot`. |
| M-02 | Pass | Browser rejected a spaced, mixed-case duplicate with “Already in this list.” API tests reject blank, duplicate, overlong, and unknown-source payloads atomically. |
| M-03 | Pass | First nonempty browser save showed an initial queued run. Repeated save and `test_profile_round_trip_and_initial_run_snapshot` left one initial run. |
| M-04 | Pass | `test_profile_edit_during_running_job_affects_only_next_run` verifies the active snapshot and subsequent-run update; browser collection showed skipped toggles from its saved snapshot. |
| M-05 | Pass | Placeholder-key API test and rendered Monitoring controls expose source names and status only. Provider environment values are absent from the profile payload and page. |

Browser review: Save and unsaved messages, inline duplicate feedback, keyboard-accessible native inputs and checkboxes, and desktop/mobile layout were observed. Screenshots: `/private/tmp/signalscout-acceptance-20260929/monitoring-desktop.png` (desktop) and `/private/tmp/signalscout-acceptance-20260929/monitoring-mobile.png` (390 × 844).

The checked-in prototype source was compared with the running screen's structure and styles. The browser explicitly rejected opening the prototype's local file URL, so direct side-by-side visual comparison and a prototype screenshot are **not verified**. No alternate route to that blocked file was used.
