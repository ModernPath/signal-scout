# SignalScout

SignalScout is a local, single-operator monitoring app. The Monitoring screen saves topics, terms, people, competitors, and six source toggles. A PostgreSQL-backed worker collects on the first nonempty save, every four hours, or on manual request. The Signal feed groups duplicate hits and supports filtering, detail, and independent Save, Interesting, and Dismiss actions. The approved prototype in `specs/design/` is a design reference.

## Repository layout

The application, specifications, and independent agents are versioned together in this repository. `agents/example-agent` is the reference architecture; `agents/signal-intelligence` implements intelligence and chat. `rag-example` remains a separate Git submodule for reference.

```sh
git clone --recurse-submodules https://github.com/ModernPath/signal-scout.git
cd signal-scout
```

For an existing checkout, run `git submodule update --init --recursive`. Credentials, database contents, and agent runtime memory are local and are excluded from version control.

## Start locally with Docker Compose

Requirements: Docker Engine with Compose v2. A fresh checkout needs one local database password.

1. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` to a nonempty, URL-safe local password (letters and digits work). Configure only provider access you have permission to use. The example `DATABASE_URL` is for a separately managed host database and is ignored by Compose.
2. From the repository root, run:

   ```sh
   docker compose up --build -d --wait
   curl -f http://127.0.0.1:8000/api/health
   ```

   If you change `WEB_PORT` in `.env`, use that port for the browser and `curl`. Open `http://127.0.0.1:8000/` for Signal feed, Monitoring, Collection, Opportunities, and Company context. Compose waits for healthy PostgreSQL, runs the one-shot Alembic migration, then starts web, the collection worker, and the intelligence worker. All use the same private `db` service. Only the web port is published, on `127.0.0.1`.

3. Inspect status and logs:

   ```sh
   docker compose ps
   docker compose logs migrate web worker intelligence-worker
   ```

4. Stop while preserving database data:

   ```sh
   docker compose down
   ```

   Restart with `docker compose up --build -d --wait`. Do not add `-v` to `down` if you want to keep the named PostgreSQL volume.

## Run migrations

The normal start runs `alembic upgrade head` before web and worker. After adding a feature migration, run it against the Compose database with:

```sh
docker compose run --rm migrate
```

This command is safe to repeat. To inspect the current revision:

```sh
docker compose exec db psql -U signalscout -d signalscout -Atc 'SELECT version_num FROM alembic_version'
```

## Source access and collection

Hacker News and public GitHub repository/issue search can run without keys. `XAIGROK_API_KEY` enables cited X and Web search. `GITHUB_TOKEN` also enables bounded public discussion lookups. `RSS_FEED_URLS` is a comma-separated list of public feed URLs. Reddit requires `REDDIT_APPROVED_ACCESS=true` and its client ID, secret, and user agent after approved API access. Gemini is reserved as an optional enrichment path and is not used by the current adapter. Missing or rejected access appears per source in Collection; successful sources still update the feed.

The worker checks for queued work every 10 seconds, uses fixed four-hour UTC slots, and records per-source counts and safe error summaries. For a single local cycle, run `.venv/bin/python -m signalscout.worker --once` with the same `DATABASE_URL` as the web process. Do not run multiple workers against the same MVP database.

## Run Python directly

For development outside Compose, use Python 3.12 or newer and a separately managed PostgreSQL database. The database must be reachable from the host; Compose intentionally does not publish its database port. Set `DATABASE_URL` to a complete `postgresql+psycopg://` URL with a URL-encoded password. Then run:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-test.lock
uv pip install --python .venv/bin/python --no-deps -e .
export DATABASE_URL='postgresql+psycopg://USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/signalscout'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn signalscout.web:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal with the same `DATABASE_URL`:

```sh
.venv/bin/python -m signalscout.worker
```

To run the integration tests, point `TEST_DATABASE_URL` at a disposable PostgreSQL database named `signalscout_ui_test` and run `.venv/bin/python -m pytest`. These tests migrate and truncate that database. Tests that need PostgreSQL are skipped when the variable is absent. Run `node tests/intelligence_ui.cjs` for intelligence rendering/action/escaping/focus checks and `node tests/ui_copy.cjs` for the small browser-copy rendering check and `node --check src/signalscout/static/app.js` for JavaScript syntax.

`requirements.lock` pins and hashes production dependencies for the container build. `requirements-test.lock` does the same for local development and tests. After changing dependencies in `pyproject.toml`, regenerate both with:

```sh
uv pip compile pyproject.toml --universal --generate-hashes --python-version 3.12 -o requirements.lock
uv pip compile pyproject.toml --extra test --universal --generate-hashes --python-version 3.12 -o requirements-test.lock
```

## Use AI intelligence in the main application

Open [Opportunities](http://127.0.0.1:8000/#opportunities). First save monitoring topics and collect signals. In **Company context**, save a company brief and paste previous company articles/posts. Then choose **Analyze signals**, select a ranked conversation, choose **Research topic**, and generate a LinkedIn/X post or reply. Edit the text, **Save revision**, and **Copy text**; drafts stay unpublished.

The same independent agent service and PostgreSQL memory power these screens. Analysis works without a key. Research and drafting need `GEMINI_API_KEY` in `.env`; `SIGNAL_INTELLIGENCE_MODEL` defaults to `gemini-2.5-flash`. Recreate services after changing environment settings. Exactly one `intelligence-worker` processes queued actions, and the UI shows their status across refreshes. Failed or interrupted actions require an explicit retry. Review cited evidence and claims before using any draft.

For a host Python run, provide `INTELLIGENCE_PROVIDER_AVAILABLE=true` to the web process when the configured worker has Gemini access, and run `python -m signalscout.intelligence_worker` in another terminal with the same database plus the Gemini key. `SIGNAL_INTELLIGENCE_DIR` can locate the agent source if the application is installed outside this repository. The web process does not need Gemini credentials. Apply all migrations through `0007_intelligence_jobs`.

See the [integration contract](specs/features/intelligence-ui/task_spec.md) and [acceptance results](specs/features/intelligence-ui/acceptance_results.md). Keep automated tests, standalone-agent tests, and live browser checks in separate disposable databases; the browser check used `signalscout_ui_browser_test`.

### Company knowledge RAG

In **Company context**, add previous content and inspect Knowledge index status. The intelligence worker indexes pasted text in application PostgreSQL using pgvector. Semantic indexing sends text to Gemini; `KNOWLEDGE_SEMANTIC_ENABLED=false` keeps lexical retrieval only. Use **Search knowledge** to inspect original passages. In **Opportunities**, select a conversation and **Refine angle** to compare prior arguments; a company brief and provider access are required. Draft source details distinguish factual research from company editorial context. All output still requires human review.

The Compose database image includes pinned pgvector on PostgreSQL 17. Back up an existing database before the image/migration update; retain the existing volume. Source changes invalidate old passages, and deletion/retention redacts retrieval excerpts. The reference `rag-example/` submodule is independently runnable and is not imported by SignalScout.

### Agent workspace

Open `http://127.0.0.1:8000/#agent` for conversational intelligence alongside actual tool activity. Suggested prompts help list opportunities, compare company content, research a selected topic and prepare drafts. Select an opportunity in the context control or use **Discuss with agent** from its detail. Replies and activity link to the same saved opportunities, sources and editable drafts as the guided screens.

Chat runs in the intelligence worker; the web process has no model key. Conversations, jobs and activity survive reloads in PostgreSQL and expire after 90 days of inactivity. Delete conversation removes its chat history/activity while retaining saved intelligence artifacts. Missing Gemini access supports explicit offline inspection/analysis commands. Interrupted or partial actions are visible and are never automatically replayed. Generated claims still require human review. See [workspace contract](specs/features/agent-workspace/task_spec.md).
