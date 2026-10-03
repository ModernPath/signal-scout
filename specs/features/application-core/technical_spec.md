# Application core — technical spec

**Parent architecture:** [MVP architecture and stack](../../architecture-tech-stack.md)  
**Delivery contract:** [Task spec](task_spec.md)

## Process and file boundaries

Use one Python package with separate entry points for FastAPI and the worker. Share typed settings, SQLAlchemy engine/session creation, and logging setup. Serve a small static core page from the application package. The approved [design reference](../../design/index.html) stays in `specs/design/` and is not packaged or served by the application. Add feature UI only alongside working feature APIs.

The worker entry point only establishes configuration and a database connection, then waits in an idle loop with graceful shutdown. The [Collection feature](../signal-collection/technical_spec.md) later adds job polling, scheduling, and adapters. Do not create a fake queue or source adapter in the core.

## Configuration and database

- Require `DATABASE_URL` using the explicit `postgresql+psycopg://` dialect. Provide separate values for local host execution and Compose service networking without committing either credential.
- Read optional provider variables only when their adapters are added later. The core starts when those variables are absent.
- Commit `.env.example` with variable names and safe placeholders; keep `.env` ignored. Reject a missing or malformed database URL with a clear startup error that does not print the secret.
- Resolve production and test dependencies into separate universal lock files with exact versions and distribution hashes. The container installs the production lock before installing the application without dependency resolution. Pin a patched Starlette release compatible with the chosen FastAPI release.
- Configure SQLAlchemy sessions with transaction cleanup at request and worker boundaries. Use UTC timestamps for future models.
- Configure Alembic from the same database setting. An initial empty migration is acceptable only to establish the revision chain; no dummy application table is required.

## HTTP surface

- During core-only delivery, `GET /` returns the static core page without mock feature data or interactions. Later feature UI may replace it alongside working APIs. Static assets use same-origin paths; no frontend build is needed.
- `GET /api/health` performs a lightweight PostgreSQL query such as `SELECT 1`. Return `200` when ready and `503` with a safe, fixed error body when unavailable.
- Configure the API route prefix and shared JSON error handling for later feature routers. Do not expose unfinished feature endpoints or return mock API data from the core.
- Return a fixed JSON 500 body for unexpected request errors and log only a safe summary, without exception text that could contain provider or database details.
- Reject cross-origin mutating requests once such endpoints exist; the core configures the same-origin policy and does not enable permissive CORS. A mutation requires either an exact matching `Origin` or `Sec-Fetch-Site: same-origin`; missing or conflicting origin evidence is rejected.
- Reject nonlocal Host headers before routing any request. Accept `localhost` and `127.0.0.1` so a browser cannot use an attacker-controlled hostname that resolves to the loopback interface as the apparent same origin.

## Local runtime

Compose has three long-running services (`db`, `web`, `worker`) plus a one-shot `migrate` service. `db` uses a named volume and health check. `migrate` waits for healthy `db` and runs `alembic upgrade head`; `web` and `worker` wait for successful migration completion. Pin the PostgreSQL image major version and Python dependencies; do not use `latest`. Bind the web port as `127.0.0.1:<port>:<container-port>` and do not publish the database port.

Run the worker as a single process. Handle termination signals so Compose shutdown closes its database connection. The web process should not run collection jobs or migrations itself. Log process startup, migration completion, and readiness without dumping environment values.

## Extension points

- Monitoring adds its tables and profile router in its own migration and module.
- Collection replaces the idle worker loop with the queued-run scheduler and adapters.
- Feed adds signal tables, routers, and a functional feed UI guided by the design reference and backed by API responses.

These feature modules use the shared settings, database session, and API conventions established here; they should not introduce another runtime or database.
