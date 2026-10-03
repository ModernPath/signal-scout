# Intelligence application UI — acceptance results

Implemented 2026-10-01 for the same trusted local operator. The main application navigation now includes Opportunities and Company context; the standalone agent stays independently runnable. PostgreSQL, deterministic ranking, and research/draft subagents are shared. No publishing action exists.

## Contract coverage

| Criterion | Result and evidence |
|---|---|
| U-01 | Pass at API boundary: brief/version/content CRUD, validation, and deletion. Browser saved fictional brief, added and edited previous content, and confirmed persistence after reload. A final temporary-content deletion reached its confirmation dialog but terminal browser verification stalled; do not claim browser deletion acceptance. |
| U-02 | Pass: API and worker analysis produces one conversation from two related fixtures, exposes scores/unknowns, timestamp, membership, provenance, prior-content match and rationale. Phase 1 saved/interesting state retained. Main feed shortcut and sidebar entry observed. Main workspace has no topics/signals and now explains setup. |
| U-03 | Pass: fake support/conflict/partial/failure tests and real Gemini grounded research through the UI; twelve evidence records with direct publisher URLs and confirmed starting sources. Reload retained the selected opportunity and queued status. |
| U-04 | Pass: all four formats generated and saved through live Gemini UI jobs. Initial LinkedIn reply failed unsupported numeric validation; stricter citation prompt and explicit retry succeeded. LinkedIn post 888 characters, reply 604; X post/reply 207 each. User edits saved versions #5 and #6, preserving original research/evidence; clipboard text and “Copied” observed. Focus moved to `draft-text-6` after save. API tests verify old snapshot citations survive new research, channel limits, and unmet prerequisites. |
| U-05 | Pass at API/worker boundary: identical requests reuse active ID, conflicting requests get 409, simultaneous submissions produce one job, stale/restart recovery fails abandoned running work without replay and retains queued work. Browser queued/loading/terminal/error states observed. |
| U-06 | Pass within local deployment: cross-origin mutation rejection, enums/IDs/input lengths/public URLs, escaped malicious source/draft rendering, safe unknown errors and actionable known validation errors, private credential boundary, localhost web port and no worker host port. Application regressions pass. |
| U-07 | Partial: actual app inspected at 1365×900 and 390×844; feature prototype inspected at 1365×900. Narrow app document width equaled viewport width, and all five navigation buttons were within it after fixing wrapping. Forms, drafts, copy and editor focus inspected on narrow view. Shared Phase 1 prototype browser comparison and feature prototype narrow comparison remain unverified after browser automation stalled on the native confirmation dialog. |

## Verification

Final deployed web, collection worker, and intelligence worker are healthy. `/api/health` returned `ok`; intelligence status reported Gemini available, zero signals, no brief, and no previous content in the real workspace. Container inspection confirmed the web process has no Gemini key and the agent image tree has no nested env files. Temporary test servers/workers were stopped after acceptance checks.

Final automated results: **68 application tests passed** (one existing Starlette/AnyIO deprecation warning), **46 standalone-agent tests passed**, both Node rendering suites and both JavaScript syntax checks passed.

- Normal tests use fake providers; live checks used public PageBreak articles and fictional company material only in a disposable database. Main workspace data was not seeded or overwritten. The application migration and local service rebuild are intentional deployment changes.
- Automated application database: `signalscout_ui_test`; standalone-agent database: `signalscout_intelligence_test`; live browser database: `signalscout_ui_browser_test`, hosted in the existing disposable `signal-scout-feature-test` PostgreSQL container. Separate databases prevent fixture truncation from interfering with live checks.
- App command: `.venv/bin/python -m pytest -q` with `TEST_DATABASE_URL` for the disposable application database. Agent command: `python -m pytest agents/signal-intelligence/tests -q` with the separate `SIGNAL_INTELLIGENCE_TEST_DATABASE_URL`, agent source on PYTHONPATH, and its Flask UI test dependencies installed in a temporary environment.
- `node tests/intelligence_ui.cjs`, `node tests/ui_copy.cjs`, and JavaScript syntax checks cover escaping, safe links, unknown components, prerequisite gates, evidence expansion, copy labels, plural copy, and focus after saving.
- Red/green cycles observed for context API, queued analysis, research/four drafts/provider failures, revisions/recovery, specific numeric errors, shell and UI rendering, provider summary/citation prompts. Narrow navigation and editor focus had failing browser observations, targeted fixes, and successful rechecks.

Screenshots were stored outside the repository in `/tmp/signalscout-intelligence-ui-n1a3Fv/`: `app-desktop.png`, `prototype-desktop.png`, `app-narrow.png`, `draft-narrow.png`, and `company-narrow.png`. Desktop screenshot preceded the last evidence-expansion/copy refinements; narrow screenshots reflect the implemented wrapping and functional draft flow. The initial attempted “narrow” capture was replaced after measuring the viewport; the accepted narrow app measurement was 390px with no horizontal overflow.

## Security and architecture review

Review used the current [OWASP Top 10:2025](https://top10.owasp.org/2025/) checklist.

| Risk | Evidence / applicability |
|---|---|
| A01 access control | One trusted local operator, existing Host and Origin/Fetch-Site protections; positive IDs and unknown-record 404s. Hosting/multiple operators remains out of scope. |
| A02 misconfiguration | Only web publishes a loopback port; dedicated worker has no published port. No wildcard CORS. Docker excludes all nested env files/caches and copies only the named agent. |
| A03 supply chain | No new production packages. Existing pinned/hash-checked application dependencies reused; agent REST research/draft subprocesses need no model SDK in the web image. Temporary Flask test dependency does not change production. |
| A04 cryptography | Gemini uses HTTPS with normal certificate checks and a request header key. Keys are environment-only; localhost database is on the private Compose network. |
| A05 injection | Parameterized SQL, Pydantic bounds/enums, escaped HTML/textareas, safe HTTP(S) links; no arbitrary executable/job name is accepted. External source instructions remain data in the existing provider. |
| A06 insecure design | Explicit queue, one active job with lock/unique index, bounded calls, required context/evidence, immutable cited snapshots, draft-only output, explicit retries. |
| A07 authentication | No sign-in by agreed local single-operator scope; authentication is required before any hosted/shared deployment. |
| A08 data integrity | Agent validates returned evidence and draft citations/length/prohibited/numeric claims; editor revisions retain original and evidence metadata and are labeled operator edits. Ranking remains a heuristic. |
| A09 logging | Persistent safe job errors/status and result IDs; arbitrary exception payloads/prompts/keys do not enter UI job responses or worker logs. |
| A10 exceptional conditions | Partial research retained and blocks drafting; failed draft leaves saved versions intact; restart/stale failure visible without automatic provider replay; unexpected API errors use existing safe handler. |

Review fixes: duplicate research prose, repeated grounding-hop work, missing numerical-citation prompt guidance, vague validation errors, hidden narrow navigation, excessive evidence scroll, singular count wording, and lost focus after saving. Relevant regression checks were rerun after these fixes.

## Remaining limits

Actual company editorial quality, ranking usefulness, and generated claim accuracy need representative company input and human review. Grounding/citation validation does not establish factual approval. Scores are conservative lexical heuristics; coverage is available score weight rather than calibrated certainty. The independent agent chat remains separate; the main UI provides the guided workflow. Scheduling and publishing are deferred. Browser deletion completion and the two outstanding prototype comparisons are not verified, for the automation reason above.
