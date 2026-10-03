# Signal collection acceptance — 2026-09-29

## Live demo repair — 2026-10-02

The user's zero-result screenshot reproduced a misleading setup state: the saved profile had no positive monitoring rules, and four adapters returned complete with zero requests. Fixed manual setup validation, initial/scheduled eligibility for exclusion-only/all-disabled profiles, and explicit unavailable outcomes for legacy empty queued jobs. Public HN/RSS/GitHub batches now commit before slow model searches. Grok 4.7 discovery uses low reasoning effort; citation validation is unchanged. Reloading `#collection` now restores that screen.

TDD: setup, public-source visibility, discovery reasoning and screen-reload regressions failed as expected before their fixes, then passed. Final application gate: **102 passed** against disposable PostgreSQL/pgvector, with only the existing Starlette/AnyIO warning. Both JavaScript verification scripts and syntax check passed.

Configured the previously empty workspace for the requested demo: AI/agents/LLM topics, RAG/Gemini/Claude include terms, Simon Willison's public Atom feed, and a labelled SignalScout project brief with repository PRD/architecture demo references. Reddit is disabled because approved access is absent. No fabricated source items were inserted.

Final manual run **#8 completed** through the actual worker:

| Source | Hits | Accepted/upserted | Requests | Status |
|---|---:|---:|---:|---|
| X | 5 | 2 | 1 | complete |
| Web/news | 5 | 5 | 3 | complete |
| Hacker News | 9 | 1 | 10 | complete |
| GitHub | 40 | 26 | 4 | complete |
| RSS | 20 | 1 | 1 | complete |
| Reddit | 0 | 0 | 0 | skipped |

Accepted counts include idempotent updates, not just new cards. The feed contains **106 real linked signals**. Run #6 exposed two X timeouts; #7 subsequently completed with five accepted X posts; #8 verified the deployed fixes. Local analysis job #2 produced 77 opportunities from the then-current feed. Real Gemini research job #3 for opportunity **#49, cloudflare/agents**, completed with six cited evidence records, including the original GitHub URL. Evidence stance remains visibly uncertain; completeness does not certify semantic accuracy.

Browser review passed at 1440×1000 and 390×844: populated Collection, feed, opportunity pagination, company passages, research evidence and draft controls; no page errors or mobile overflow. Compared the shared prototype at matching viewports. Evidence under `/tmp/signalscout-demo/`: `collection-desktop.png`, `feed-desktop.png`, `opportunity-desktop.png`, `opportunity-mobile.png`, `prototype-desktop.png`, `prototype-mobile.png`, and live run/research JSON.

Security/architecture: loopback and same-origin controls, parameterized SQL, safe errors, source URL/citation validation, worker-only credentials and bounded responses remain intact; no new dependencies. The company-knowledge review covers the same applicable OWASP boundaries. Live provider calls stayed outside regression tests.

**Pending:** automatic approval review rejected an initial combined demo command because it flagged possible company-document transmission to Gemini. Verified that analysis is local and research sends public source titles/URLs only; those narrower actions were approved and completed. The explicit approval question for sending labelled demo brief/documents to Gemini remains pending. Angle refinement and draft generation for this new live demo have not been run while awaiting that answer; earlier synthetic verification does not substitute for live acceptance.

Environment: controlled adapters against disposable PostgreSQL databases; local app on port 8001 for browser acceptance. External smoke checks were bounded and separate from the normal tests.

| Case | Result | Evidence |
|---|---|---|
| C-01 | Pass | Controlled UTC clock and `test_one_scheduled_run_per_utc_slot` produced one run for a slot. Worker cycle test covered processing initial then scheduled work. The browser showed a completed scheduled run with the preceding manual and initial runs in history. |
| C-02 | Pass | Automated queued/running reuse test returned the same run ID. Browser manual refresh showed one queued manual run after two clicks. |
| C-03 | Pass | Fixture HN and GitHub items persisted while Web timed out. Browser showed `partial`, the safe Web timeout, 2 HN and 1 GitHub accepted hits, and skipped disabled sources. |
| C-04 | Pass | Disabled sources appeared as skipped in the browser. Missing X key and RSS URL produced source-specific unavailable codes in the automated test. |
| C-05 | Pass | Malformed worker candidates and uncited AI items were rejected; rejection counts were tested for invalid GitHub and RSS hits. |
| C-06 | Pass | Repeat external ID remained idempotent; transient timeout retried once under the source budget. Incremental cursor and interrupted-run recovery tests passed. |
| C-07 | Pass | Run API and browser showed safe codes/messages; a fixture secret in a thrown provider error was absent. Code review found no raw provider payload or credential logging. |
| C-08 | Not verified in full | Live smoke: HN 5 hits/1 candidate, GitHub 20/20, xAI Web 5/4 cited candidates, X 5/5 cited posts, and RSS 20/20 linked items from the [Python project's documented public feed](https://blog.python.org/2026/03/the-python-insider-blog-has-moved/), using a temporary smoke-check setting. A public page fetch succeeded with validated DNS pinning. Reddit had no approved OAuth access; local app RSS still has no configured feed URL; token-enabled GitHub discussions were fixture tested but not live checked. |

Browser screenshots: `/private/tmp/signalscout-acceptance-20260929/collection-desktop.png` (partial), `/private/tmp/signalscout-acceptance-20260929/collection-scheduled-desktop.png` (scheduled complete with manual/initial history), and `/private/tmp/signalscout-acceptance-20260929/collection-mobile-final.png` (390 × 844). A complete, partial, and queued/manual status were checked through tests and browser observations. The prototype's local file URL was rejected by browser policy, so direct prototype comparison and its screenshot are **not verified**.

The worker is configured for one local instance. Its Docker image built successfully; live provider availability and rate limits remain dependent on configured access.
