# Agent workspace acceptance — 2026-10-03

## Verification

- Application regression suite: **109 passed** against disposable PostgreSQL 17/pgvector. Standalone suite: **47 passed** against its separate migrated disposable database. Existing Starlette/AnyIO deprecation warning only. An initial standalone invocation used the wrong database-variable name and skipped 20 cases; the corrected full run passed all 47.
- `node tests/agent_workspace_ui.cjs`, `node tests/intelligence_ui.cjs`, `node tests/ui_copy.cjs` and JavaScript syntax checks passed. New API/worker contracts first failed for absent routes/orchestrator, then passed. Additional regressions covered action budgets, saved refinement references and conversation restoration. The first database invocation occurred before the test container was ready; that setup error was not counted as red-green evidence.
- Fake external models/providers exercise the actual service and PostgreSQL lifecycle for selected research → company retrieval/refinement → LinkedIn draft, artifact IDs/citations, partial failures, no replay, tool selection validation, observable in-progress events, interruption closure, UUID idempotence, conflicts, same-origin rejection, deletion and expiry.
- Real Gemini through the actual main application queue: session **#2**, job **#5**, completed in about 3.2 seconds using `list_opportunities` and producing a grounded ranking response. Persisted start/completion events and five actual opportunity references are present. `/tmp/signalscout-agent-workspace/live.json` records the safe response and activity. This smoke used saved ranking metadata only; it did not transmit company document passages or generate new research/drafts.

## Contract review

| Requirement | Result | Evidence |
|---|---|---|
| W1 prominent usable chat | Pass | Main navigation, suggested prompts, context selector, composer, session controls; browser desktop/mobile |
| W2 queue/reload/idempotence | Pass | Atomic user-turn/job enqueue, UUID reuse and conflict tests, actual queued turn and reload into saved session |
| W3 shared tools and gates | Pass technically | Existing service wrappers; selected-topic real persistence with external fixtures; offline and model-failure tests. New live research/draft editorial quality was not established. |
| W4 actual activity | Pass | Started event observable during provider call; persisted ordered completion/failure; real Gemini tool event; named subprocess labels correspond to actual service runner |
| W5 connected results | Pass | Reply cards and activity references link to existing details; browser opportunity navigation and Discuss with agent context; source/draft/passage rendering contracts |
| W6 limits/privacy/recovery | Pass for local operator | Bounded requests/history/tools/output, safe errors, no replay, escaped text, selection validation, FK cleanup and same-origin tests |

## UI/design evidence and fixes

Used Playwright with local headless Chrome because native computer-use tooling failed in the preceding repository session. Reviewed actual application, feature prototype and shared design at 1440×1000 and 390×844. Actual chat submission/reload, activity expansion, result navigation, opportunity context, suggested prompt keyboard focus, conversation switching/deletion and mobile overflow passed. No page errors. Feature prototype supplies the information flow; the shared product shell stays in place.

Review found and fixed conversation IDs lost by initial navigation, a 1094px intrinsic opportunity dropdown overflowing mobile, result cards hidden only inside collapsed activity, and opportunity context susceptible to polling overwrite. Explicit unpinning is now preserved and stale asynchronous responses ignored. Final controls and coordinator/subagent labels were polished to fit the shared shell.

Temporary screenshots: `/tmp/signalscout-agent-workspace/chat-desktop.png`, `chat-mobile.png`, `empty-mobile.png`, `prototype-desktop.png`, `prototype-mobile.png`, `shared-design-desktop.png`, `shared-design-mobile.png`. The original live browser attempt timed out on the URL restoration bug although its Gemini job had completed; acceptance comes from the subsequent successful browser review using that saved turn.

## Security and architecture

Reviewed against [OWASP Top 10:2025](https://top10.owasp.org/2025/):

| Category | Review evidence |
|---|---|
| A01 access control | Trusted local operator; loopback-only port and same-origin mutations. No hosted or multi-user claim. |
| A02 configuration | Existing web receives capability flags only; provider keys stay in intelligence-worker. |
| A03 supply chain | No new dependency; standard-library REST adapter, existing pinned lockfile/images. |
| A04 cryptography | Fixed HTTPS provider endpoint and header-scoped key; private local PostgreSQL. |
| A05 injection | Bound SQL, schema/argument validation, escaped reply text before limited bold formatting, safe artifact URLs and untrusted-source instructions. |
| A06 design | Explicit selected-opportunity action gates, eight-call budget, no publishing/context mutation tools, preserved results without automatic replay. |
| A07 authentication | Existing localhost-only single-operator deployment retained; shared hosting needs separate authentication design. |
| A08 integrity | Actual tool events and saved artifact references; atomic submission-token deduplication; validated research/drafts reuse existing service contracts. |
| A09 logging | No raw model payload/tool transcript/key logging; safe errors. Jobs store turn IDs rather than copies of message bodies. |
| A10 exceptions | Partial chat response after model failure, interruption events closed, bounded deadlines/timeouts and session cleanup tested. |

No alternate database, second queue, or publishing surface was introduced. Main REST chat and independent SDK chat share service tool wrappers. Model answer text is editorial/model output; activity is the authoritative execution record. Provider latency and subjective editorial quality cannot be guaranteed by the tests.

## Rollout

Existing database backed up privately at `/tmp/signalscout-before-agent-workspace.dump`, migration `0012_agent_workspace` applied successfully, main web/intelligence worker rebuilt and healthy. The running application exposes `#agent` and the saved real Gemini demo at `#agent/2`. Existing collection and guided intelligence data remain available. Company-document live editorial acceptance from the previous demo remains separate; no approval is inferred from elapsed time.
