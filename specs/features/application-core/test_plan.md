# Application core — test plan

**Delivery contract:** [Task spec](task_spec.md)  
**Status:** Implemented and verified on 2026-09-29 with a disposable PostgreSQL 17 database and local Docker Compose stack.

Follow the repository's TDD rule when implementation begins. The first runnable behavior should have a failing test before production code. Use a disposable PostgreSQL instance for integration checks and keep provider credentials out of the test environment.

| Case | Level | Scenario | Expected result |
|---|---|---|---|
| CORE-01 | Integration | Start the web app with a reachable migrated PostgreSQL database. | `GET /api/health` returns `200`; the request opens and closes a DB session cleanly. |
| CORE-02 | Integration | Make PostgreSQL unavailable after startup. | `GET /api/health` returns `503` and a safe fixed error; no connection string or password appears. |
| CORE-03 | HTTP/UI | Request `/` and its static assets. | During core-only delivery, a minimal core page renders. After feature UI integration, the live page and assets render without prototype fixtures, mock feature controls, or simulated collection actions. |
| CORE-04 | Configuration | Omit `DATABASE_URL`, then provide a malformed value. | Startup fails clearly without logging the secret. Missing optional provider keys do not block startup. |
| CORE-05 | Migration | Apply migrations to a fresh database and then apply them again. | Both commands succeed; the second is idempotent and no user data is deleted. |
| CORE-06 | Process | Start the worker against the migrated database, leave it idle, then terminate it. | It remains alive without source keys, logs readiness, and exits cleanly. |
| CORE-07 | Compose | Start the full stack from documented commands with a fresh volume. | DB health precedes migration; migration precedes web/worker; only the web port is reachable from the host. |
| CORE-08 | Persistence | Restart the stack without deleting the named volume. | Database state and Alembic revision persist. |
| CORE-09 | HTTP/security | Send read and mutating requests with an attacker-controlled Host, including a matching Origin. | Both are rejected before routing; local Host requests continue to work. |
| CORE-10 | Dependency/build | Build the container from the production lock, install the test lock, and audit both lock files. | Installs verify distribution hashes, the build and tests pass, and the current advisory audit reports no known vulnerabilities. |
| CORE-11 | HTTP/error | Raise an unexpected exception from an API route with sensitive text in the exception. | Response is a fixed JSON 500 body; the exception text appears in neither response nor normal logs. |
| CORE-12 | HTTP/security | Send mutations without origin evidence, with a matching Origin, with same-origin Fetch Metadata, and with a foreign Origin. | Missing and foreign evidence return 403; both same-origin forms reach routing. |

## Exit criteria

CORE-01 through CORE-06, CORE-09, CORE-11, and CORE-12 pass in targeted automated checks. CORE-07 and CORE-08 pass as local Compose integration checks. CORE-10 passes in locked installation and advisory checks. The documented start command reproduces the working stack on a clean checkout. No feature behavior is claimed complete by these core checks.

## Verification record

- `TEST_DATABASE_URL=... .venv/bin/python -m pytest -q`: 11 passed. The integration database ran in a disposable PostgreSQL 17 container.
- `docker compose --env-file <temporary-test-env> up --build -d --wait`: PostgreSQL, web, and worker became healthy. Migration completed before web and worker started. `/api/health` returned 200. The original `/` prototype check was superseded by the core-only page requirement.
- `docker compose ps`: PostgreSQL had no published host port; the web port was bound to `127.0.0.1`.
- Stopping PostgreSQL after startup changed `/api/health` to 503 with the fixed body `{"detail":"Database unavailable"}`.
- A full `docker compose down` followed by `up -d --wait` retained the Alembic revision and a temporary marker row. Normal service logs contained no temporary password or database URL.
- Core-only correction: the revised CORE-03 test failed against the served prototype, then passed after replacing the app's static page. `docker compose up --build -d --wait` rebuilt the running stack; `/` served the core page, `/api/health` returned 200, and the refreshed browser tab showed no prototype controls or sample signals.
- Security and dependency correction: CORE-09 failed before host validation (requests reached routing with 404), then passed with a local Host allowlist. The final container built from the hashed production lock; the hashed test lock installed in a disposable test container. The PostgreSQL-backed suite passed with 19 tests and deprecations treated as errors. On 2026-09-29, `pip-audit` reported no known vulnerabilities in either lock. Stopping PostgreSQL returned the fixed 503 response; restarting Compose retained the Alembic revision and a temporary marker row.
- Shared error handling correction: CORE-11 first returned plain-text 500, then returned the fixed JSON body without logging sensitive exception text. After rebuilding the isolated stack, the current PostgreSQL-backed suite passed with 28 tests and deprecations treated as errors.
- Origin evidence correction: CORE-12 first reached routing with no Origin or Fetch Metadata, then returned 403 after the middleware change. Matching Origin and `Sec-Fetch-Site: same-origin` requests reached routing; a foreign Origin returned 403 in the isolated Compose stack. The core worker shutdown test now clears the disposable feature queue before starting, so queued collection work cannot enter the network in that test.
- Repeat review after the feature UI replaced the temporary core page: the isolated PostgreSQL-backed suite passed with 36 tests and deprecations treated as errors. The rebuilt Compose stack reported healthy DB, web, and worker services; `docker compose ps` showed only the web port published on `127.0.0.1`. Chrome loaded `/` and `/app.js` with successful API requests and no console errors. After clearing test rows from the disposable review database, the feed, monitoring, and collection screens displayed live empty states. Desktop screenshots are in `/tmp/signalscout-core-repeat-review/`. Keyboard focus was visibly indicated on the collection action.
- Remaining verification limits: the local prototype URL and viewport override were rejected by browser policy during this review, so a matching desktop/narrow prototype comparison remains unverified. This workspace has no `.git` metadata, so tracked-file status of secrets cannot be established here; `.gitignore` does exclude `.env`.
