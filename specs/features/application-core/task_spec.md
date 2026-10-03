# Application core — task spec

**Parent architecture:** [MVP architecture and stack](../../architecture-tech-stack.md)  
**Order:** Build this foundation before [Monitoring](../monitoring-profile/task_spec.md), [Collection](../signal-collection/task_spec.md), and [Feed](../signal-feed-triage/task_spec.md).

## Outcome

Start SignalScout locally as a web process, a worker process, and PostgreSQL from one codebase. The web process serves a minimal application-core page, connects to PostgreSQL, and reports readiness. The worker starts and waits for future collection work. Feature screens, APIs, and source integrations are built on this foundation afterward. The approved prototype remains a design reference in `specs/design/`; it is not served by the running application.

## Implementation tasks

1. [x] Create the Python project, pinned dependency manifest, and shared package layout for web, worker, configuration, and database access.
2. [x] Add typed configuration loaded from environment variables, plus `.env.example` containing names but no secrets.
3. [x] Configure SQLAlchemy with `psycopg` and Alembic. Make migrations run before either long-running process starts; leave feature tables to their own feature migrations.
4. [x] Create the FastAPI entry point, serve a minimal core page at `/`, and expose `GET /api/health` with a real PostgreSQL readiness check.
5. [x] Create a separate worker entry point that starts, connects to PostgreSQL, stays alive while idle, and shuts down cleanly. It does not poll collection jobs yet.
6. [x] Add Dockerfile and Compose setup for PostgreSQL, a one-shot migration task, web, and worker. Persist PostgreSQL data and publish only the web port to `127.0.0.1`.
7. [x] Document the exact local start, stop, migration, and environment setup commands in the repository README.

## Acceptance criteria

- A new developer can start the local stack from documented commands after supplying a local database password. PostgreSQL is persistent; the web and worker share one configured database.
- Database readiness and migrations complete before web and worker are marked ready. Restarting the stack does not rerun destructive setup or erase data.
- During core-only delivery, `/` renders only an application-core page, with no example signals, mock monitoring form, simulated collection, or feature navigation. Later feature UI replaces that temporary page when backed by working APIs; the approved prototype remains only in `specs/design/`.
- `GET /api/health` returns success only when the web process can query PostgreSQL; it returns an error status when the database is unavailable.
- The worker starts without source credentials, remains healthy while idle, and exits cleanly on shutdown.
- Secrets stay out of tracked files, browser responses, and normal logs. The database has no host-exposed port, the web port binds to localhost, and the web process rejects requests with nonlocal Host headers.

## Boundaries

The core does not add profile CRUD, collection jobs or adapters, normalized signals, feed APIs, triage persistence, authentication, or hosted deployment. Those belong to the later feature specifications. No placeholder domain tables are needed solely to prove migrations work.
