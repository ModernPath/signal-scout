# Company knowledge RAG — acceptance results

**Date:** 2026-10-02. **Scope:** all three planned RAG slices; semantic signal clustering remains deferred. Technical implementation is delivered; representative company editorial approval is pending.

## Verification

- Application regression gate: **98 tests passed** against disposable PostgreSQL 17/pgvector (including new RAG tests). Agent regression gate: **47 passed** against a separate disposable migrated database. Both show only the existing Starlette/AnyIO deprecation warning.
- `node tests/intelligence_ui.cjs`: passed rendering, escaping, unsafe-link handling, capability gates, company-screen job/errors, retry availability and revision focus checks. `node --check` and agent Git whitespace checks passed.
- Fixed real-embedding evaluation: **18/20 hybrid top-five hits**, versus **17/20 lexical**. Fixture: `tests/fixtures/knowledge_retrieval.json`; full results: `/tmp/signalscout-rag-evaluation.json`. Two paraphrase queries missed: prohibited bot operations and promotional content as proof. This meets the proposed synthetic gate but does not establish recall on the operator's company corpus.
- Real Gemini on synthetic company context: incremental indexing → semantic passage retrieval → cited angle refinement → complete grounded research → validated X draft. Latest successful continuation used six embedding requests and two generation requests after the initial eight-embedding/two-generation run. Initial partial research correctly blocked drafts; earlier runs exposed malformed model fields and motivated typed schemas and exact prior-claim validation. Report: `/tmp/signalscout-rag-live-report.json`.
- Main browser actions used the actual shared subagent path: queued search, refinement, X draft, editor revision and clipboard copy passed. A deletion URL regression was reproduced and fixed. Source removal is verified in API tests and browser review. Synthetic records stayed in disposable databases, not the application's workspace.
- Current application database backup restored successfully to disposable `signalscout_restore_test`, then upgraded through `0011_chunker_versions`. Repeat migration/data-preservation tests passed. Backup is a private temporary dump; no dump or credential is committed.

## Live application follow-up (2026-10-05)

- Live refinement on the application workspace's project-document company context initially failed: Gemini returned HTTP 400 because the response schema enumerated every passage sentence. The earlier synthetic context was too short to expose this. Prior claims are now selected by numbered quote; two provider tests cover the compact schema and forged quote numbers.
- After the fix: **110 application tests passed** against disposable PostgreSQL 17/pgvector; agent suite **27 passed, 20 skipped** (its database-backed tests were not run in this pass); `node tests/intelligence_ui.cjs` passed.
- Real Gemini through the main application queue for opportunity #49 (`cloudflare/agents`): refinement job #9, LinkedIn draft job #10 and X draft job #11 all completed, saving enrichment #1 and drafts #1–#2 with six research citations each. This run was API-driven; no new browser pass was made.
- Editorial quality remains unapproved. In this run all three comparisons cited one architecture chunk, and one selected "prior claim" was a section heading rather than an argument; the drafts restate the research without a distinct company angle.

## Contract coverage

| Criterion | Result | Evidence / limitation |
|---|---|---|
| AC1 shared indexing lifecycle | Pass | Transactional source triggers, idle-worker test, unchanged-input provider-call counters, saves during active jobs |
| AC2 original-passage retrieval | Pass on synthetic gate | Real pgvector SQL, lexical/hybrid tests, 18/20 real-embedding evaluation, original offsets and IDs |
| AC3 repeated versus fresh claims | Technical safeguards pass; editorial judgment not verified | Exact source quotes, forged/invented claim rejection, no-match uncertainty, provisional lexical novelty. Ten representative company claim pairs still require editorial review. |
| AC4 Why us / angle | Technical path pass; editorial quality pending | Real Gemini/subagent refinement and source inspection; uncertainty and company-brief controls. No automatic guarantee of a genuinely fresh argument. |
| AC5 research-grounded drafts | Technical pass; semantic entailment needs review | Separate citation namespaces, selected-research isolation, real draft and editor revisions, expired/numeric/prohibited claim rejection. Models can still misinterpret valid sources. |
| AC6 source lifecycle | Pass | Delete/edit/expiry tests, stale embedding/generation commit checks, database JSON/query redaction, source-removal UI |
| AC7 failure/offline behavior | Pass | Missing capability, bad vectors, provider failure, preserved old vectors, lexical/offline chat and visible retry/errors |
| AC8 shared interfaces / worker | Pass | Main queued API, actual subprocess jobs, independent CLI/API/UI/chat contracts, explicit subagent database isolation |
| AC9 provenance/version changes | Pass for delivered design | Immutable retrieval hits, separate draft FKs, preserved editorial revisions, model and chunker rebuild tests; deterministic scores intentionally remain unchanged |

## Browser/design review

Native computer-use tooling failed to start its Node runtime; Playwright with local headless Chrome was used instead. Compared the shared Phase 1 prototype, feature prototype and real main UI at 1440×1000 and 390×844. Navigation, readable source passages, wrapped controls, no horizontal overflow, escaped content, clipboard copy and editor focus were exercised. The existing product shell is retained; the feature prototype is an information-flow reference.

Temporary evidence under `/tmp/signalscout-rag-browser/`:

- `company-desktop.png`, `opportunity-desktop.png`, `opportunity-mobile.png`
- `prototype-desktop.png`, `prototype-mobile.png`, `shared-design-desktop.png`
- `search-desktop.png`, `draft-sources-desktop.png`, `refinement-mobile-viewport.png`
- `deletion-company-mobile.png`, `source-removed-mobile.png`

Review found and fixed hidden Company-context job errors, disabled retry controls after a failed submission, deletion changing the current URL, insufficient draft API provenance, expired-evidence fallback, stale generation commits, and dependence on an unrelated ambient subagent database URL. A browser rerun approval timed out once; the allowed retry succeeded. No acceptance is inferred from that timeout.

## Security and architecture review

Reviewed against [OWASP Top 10:2025](https://top10.owasp.org/2025/):

| Area | Evidence |
|---|---|
| A01 access control / A07 authentication | Existing trusted local operator only; loopback web, private DB, same-origin mutation middleware. Hosted use is not supported. |
| A02 configuration | Pinned PG17/pgvector image; main web receives capability flags, not model credentials; explicit database boundary for subprocesses |
| A03 supply chain | pgvector pinned by digest; no runtime imports/copied source/dependencies from the example; existing application lockfile unchanged |
| A04 cryptography | Fixed HTTPS provider transports; keys scoped to worker/subagents and excluded from API/logs. No new remote document store |
| A05 injection | Bound SQL parameters, escaped/Jinja-autoescaped passages, validated HTTP(S) links, untrusted-source prompts, structured output with membership and quote checks |
| A06 design | Separate editorial/factual source roles; no publishing; incomplete coverage/unknown novelty visible; human claim review remains necessary |
| A08 integrity | Versioned chunks/configs, source hash and eligibility checks at commit, exact quote validation and immutable retrieval/draft lineage |
| A09 logging | Safe job/provider/subagent errors; no raw prompts, secrets or provider payloads in application logs |
| A10 exceptional conditions | Timeouts, input/output limits, failed indexing/retry states, no automatic provider-job replay, stale-job recovery and lexical fallback |

## Remaining acceptance inputs

Representative company brief/content and at least ten editorial claim comparisons are required for company acceptance. Exact semantic entailment and fresh-angle quality cannot be established by citation syntax or the synthetic retrieval benchmark. Durable provider token/cost accounting and large-corpus performance tuning are not implemented; provider work is bounded by request/input/output/time limits. Full schema downgrade of versioned chunk history is intentionally unsupported; operational rollback uses lexical mode or the verified backup.

## Local rollout

The main application at `http://127.0.0.1:8000` and existing standalone agent UI/API at ports 5013/8013 were rebuilt and started on 2026-10-02. All six running services are healthy. The preserved application database is at `0011_chunker_versions` with pgvector 0.8.7. The image change exposed a libc collation mismatch; `REINDEX DATABASE` followed by `REFRESH COLLATION VERSION` resolved it. Before/after counts match: zero signals, zero company-content records, zero briefs, and three collection runs. No synthetic test records were added to this workspace.

Health and knowledge-status endpoints returned successfully with embedding capability available. A read-only browser check verified the deployed Company-context knowledge controls; screenshot: `/tmp/signalscout-rag-browser/deployed-company.png`. The private pre-rollout backup is `/tmp/signalscout-before-rag-rollout.dump`. Temporary browser server and test database were stopped after verification. The operator can begin by saving a company brief and previous content, then configuring Monitoring to collect signals.
