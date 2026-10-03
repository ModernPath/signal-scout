# Monitoring, collection, and feed feature review — 2026-09-29

The case-by-case contract trace and browser evidence are in [Monitoring](features/monitoring-profile/acceptance_results.md), [Collection](features/signal-collection/acceptance_results.md), and [Feed](features/signal-feed-triage/acceptance_results.md). Review used the Phase 1 PRD, MVP architecture, each feature's task/technical/test documents, and the checked-in prototype source. The running app was exercised at desktop and 390 px widths. The prototype's local file URL was explicitly rejected by browser policy; direct browser comparison and a prototype screenshot remain unverified.

## Findings and fixes

| Severity | Finding | Resolution |
|---|---|---|
| Medium | Public page fetch checked DNS, then the HTTP client resolved the name again, allowing a DNS change between validation and connection. | Pinned the connection to a validated public IP while retaining the hostname for TLS certificate verification, rejected redirects, and verified with a failing-then-passing test and a public HTTPS smoke check. |
| Low | A cached client script could leave the browser with an old version after deployment. | Added a content version to the script URL and `no-store` responses; tested headers and markup. |
| Low | A signal-detail dialog could send keyboard focus behind the open drawer after the last link, and polling could replace the invoking button before focus returned. | Added Tab/Shift+Tab focus wrapping and restoration to the current card after polling. Failing-then-passing rendering tests and a browser check after an 8-second poll verified both. |
| Low | One-item counts rendered as “1 signals” or “1 hits.” | Added a failing rendering test and corrected the copy. |
| Low | Returning to the feed after new items arrived refreshed cards but left Found and Duplicate summary counts stale. A one-point signal also displayed “1 points.” | Refreshed the summary on feed navigation while preserving New for the current visit; made standard metric units singular at one. Focused tests and browser checks passed. |
| Low | An out-of-range numeric publication timestamp from a provider could raise an exception and fail its entire source run. | Treat it as an unavailable item time; verified with a failing-then-passing adapter test. |

No unresolved implementation defect was found in the covered local MVP flows. Remaining verification limits are approved Reddit access, the unconfigured RSS feed in the running app, and direct browser comparison to the approved prototype. The RSS adapter itself returned linked items in a separate public-feed smoke check.

## OWASP Top 10:2025 checklist

| Category | Review evidence and applicability |
|---|---|
| A01 Broken Access Control | The agreed one-operator MVP has no sign-in. Compose publishes the web port only on `127.0.0.1`; TrustedHost accepts local hosts, and mutations reject cross-origin requests. Shared or public deployment remains outside this design. |
| A02 Security Misconfiguration | FastAPI docs are disabled, unexpected errors return a generic message, DB is private to Compose, and the web port is loopback bound. The production Python base image is digest pinned; Postgres uses a major-version tag. |
| A03 Software Supply Chain Failures | Production/test requirements are hash locked; Docker package installation requires hashes. Dependencies and container builds were exercised. Provider data is not executed as code. |
| A04 Cryptographic Failures | Provider API credentials stay in worker environment variables. Provider calls and verified public-page fetches use HTTPS when their URL is HTTPS, with default TLS certificate checks. PostgreSQL encryption at rest is outside this local MVP. |
| A05 Injection | Profile and feed SQL uses parameters; the only interpolated state-column name comes from a validated three-field model. External text is HTML escaped in the UI. Unsafe links are rejected. |
| A06 Insecure Design | Single trusted operator and local binding are explicit. Collection has per-source request caps, a single worker, bounded retries, and citation-backed xAI candidates. Public page fetches validate URL/DNS and pin a public address. |
| A07 Authentication Failures | No authentication is present by the approved local-only product model; this must change before network exposure or multiple operators. Reddit uses approved OAuth credentials in the worker environment. |
| A08 Software or Data Integrity Failures | xAI candidates need matching real URL citations; source items require stable URLs and are idempotent. Historical source provenance is retained. AI text remains untrusted content for operator review. |
| A09 Security Logging and Alerting Failures | Worker and web log lifecycle/safe failures without tokens, headers, or provider payloads. Collection UI shows source-level failures and timestamps. External alerting is outside this local MVP. |
| A10 Mishandling of Exceptional Conditions | Provider exceptions are classified into safe per-source status; successful source commits survive another source's failure. Stale worker runs recover without repeating completed source rows; API exceptions return a generic response. |

## Architecture and operational review

- Schema and API contracts match the feature documents after recording two implementation decisions: `signal_topic` keeps matched text so history survives profile replacement, and the HTTP adapters use the Python standard library transport instead of `httpx`.
- A single database-backed worker claims work and commits each source independently. UTC slot uniqueness, active-run reuse, source snapshots, incremental cursors, and interrupted-run recovery were covered by integration tests.
- HN, GitHub, RSS, Reddit, and xAI source modules are separate; the shared transport and normalization layer is in `adapters.py`. GitHub optional discussion failure retains REST results. Missing credentials produce safe unavailable statuses.
- Browser review covered save/unsaved state, duplicate rule validation, manual collection, partial status, feed filters, detail/provenance, triage, malicious source text, desktop/mobile overflow, and empty feed state. Screenshots are in `/private/tmp/signalscout-acceptance-20260929/` and enumerated in the feature acceptance files.

## Verification

Automated checks: 55 passing `pytest` cases against disposable PostgreSQL (one third-party deprecation warning), passing `node tests/ui_copy.cjs`, `node --check src/signalscout/static/app.js`, `docker compose build web worker`, and a local worker `--check` against the isolated acceptance database. External smoke checks ran separately with bounded budgets. C-08 and F-08 remain partially unverified for the reasons above; no live Reddit result is claimed.
