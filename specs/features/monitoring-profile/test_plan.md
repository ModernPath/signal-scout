# Monitoring profile — test plan

**Behavior:** [Task spec](task_spec.md)  
**Status:** Executed 2026-09-29; see [acceptance results](acceptance_results.md)

| Case | Scenario | Expected result |
|---|---|---|
| M-01 | Save all rule kinds and source toggles, then restart web and worker. | The same profile loads from PostgreSQL. |
| M-02 | Submit blank, duplicate-with-different-case, overly long, and unknown-source values. | The whole invalid update is rejected; the prior profile remains intact and the UI shows a useful error. |
| M-03 | Save the first non-empty profile twice. | Exactly one `initial` run exists. |
| M-04 | Change rules and toggles while collection is running. | The active run uses its original snapshot; the next run uses the update. |
| M-05 | Inspect profile API responses and rendered controls with placeholder provider keys configured. | No key value is exposed. |

Use the real API and a disposable PostgreSQL database for persistence cases. Use a controlled worker for M-04. All five cases passed in automated checks; M-01 and M-02 were also exercised in the running browser.
