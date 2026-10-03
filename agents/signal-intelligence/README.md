# SignalScout intelligence agent

Standalone Phase 2 agent built from [`../example-agent/`](../example-agent/) with chat, skills, tools, PostgreSQL memory, subagents, local API, and local UI. It runs independently and also powers the main SignalScout Opportunities and Company context screens through the shared service; it never publishes content. The contract and current acceptance limits are in the [task](../../specs/features/intelligence-agent/task_spec.md), [technical spec](../../specs/features/intelligence-agent/technical_spec.md), [test plan](../../specs/features/intelligence-agent/test_plan.md), and [results](../../specs/features/intelligence-agent/acceptance_results.md).

## Contract

- **Inputs:** Phase 1 signals, source items, topics, and dismissed flags in the application PostgreSQL database; a manually supplied company brief and prior content; optional `GEMINI_API_KEY` for grounded research and drafting.
- **Outputs:** Versioned analysis runs, conversations, opportunity scores and rationale, research evidence, and unpublished drafts in the same PostgreSQL database. CLI prints one JSON success/error object.
- **Permissions and side effects:** Reads Phase 1 records; writes only Phase 2 tables. Context edits, analysis, chat, research, and drafting persist records. Model chat, research, and drafting can call an external model. They send the selected source titles/URLs or company context needed for the requested action; use only company material approved for that provider.
- **Offline behavior:** Brief/content management, clustering, ranking, and opportunity inspection work without a model key. Research and drafting give an explicit provider-unavailable error.
- **Memory:** PostgreSQL is the only persistent store. The operator can inspect and delete private context; replacement lineage is scrubbed on deletion. Chat and research excerpts expire after 90 days through the cleanup command. Drafts remain as review artifacts.
- **Surfaces:** Direct and conversational CLI, JSON tool CLIs, localhost API, and independent localhost UI. No background scheduler or publish operation.

## Agent structure

The [technical spec](../../specs/features/intelligence-agent/technical_spec.md#folder-map-and-boundaries) owns the detailed file map. `intelligence_core.py` holds pure grouping and scoring; `intelligence_service.py` coordinates shared use cases. `memory/` is a PostgreSQL adapter and inspection CLI, not a JSON note store. The three subagents handle topic analysis, evidence research, and one draft variant. Chat tools, direct tools, API, and UI call the same service. The agent reads Phase 1 tables and writes only Phase 2 tables.

## Setup

Application migrations `0005_intelligence` and `0006_agent_memory` own the Phase 2 schema. Apply them with the normal application Alembic task before running the agent. Supply a `postgresql+psycopg://` `DATABASE_URL` for the same private application database. The database is not published by Compose; run the agent on the Compose network or use an independently configured local Postgres connection. Never use the production database for tests.

From the SignalScout root, start the independent local UI and API with the optional Compose overlay:

```bash
docker compose -f compose.yaml -f agents/signal-intelligence/compose.yaml up --build -d --wait agent-ui agent-api
```

The [agent UI](http://127.0.0.1:5013/) and [API health endpoint](http://127.0.0.1:8013/health) use loopback host ports. The local UI has no login; use it only as one trusted operator. The agent's ignored `.env.local` can define its own `DATABASE_URL`, `GEMINI_API_KEY`, and `SIGNAL_INTELLIGENCE_MODEL` for direct local runs. It never searches parent folders for secrets. The Compose overlay defaults to `gemini-2.5-flash`.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://.../signalscout'
.venv/bin/python signal_intelligence.py brief set /path/to/brief.json
.venv/bin/python signal_intelligence.py content add /path/to/article.json
.venv/bin/python signal_intelligence.py analyze
.venv/bin/python signal_intelligence.py opportunities list
.venv/bin/python signal_intelligence.py opportunities show 1
.venv/bin/python signal_intelligence.py --chat --offline
```

Example brief JSON:

```json
{"description":"Security platform for AI agents","audience":"Security leaders","expertise":"Agent security","point_of_view":"Verify agent actions","voice":"Practical and specific","avoid_claims":"Guaranteed safety"}
```

Example prior content JSON:

```json
{"title":"How we verify agent actions","text":"A short excerpt or full prior article text","url":"https://company.example/article","channel":"blog"}
```

With an explicitly configured `GEMINI_API_KEY`, run:

```bash
.venv/bin/python signal_intelligence.py research 1
.venv/bin/python signal_intelligence.py draft 1 --channel linkedin --format post
.venv/bin/python signal_intelligence.py draft 1 --channel x --format reply
```

Run the other two channel/format combinations in the same way. Drafts are saved for human review only. Model output is validated for known evidence IDs, channel length, prohibited phrases, and numeric claims, but editorial fact checking remains necessary.

Run `brief delete`, `content replace/delete`, and `python memory/memory.py cleanup` to manage private context and retention. Individual scripts in `tools/` expose JSON envelopes for automation. Grounded research keeps only cited source segments, resolves Google citation redirects to public publisher URLs, labels explicit support/conflict claims, and records safe partial failures. If no original source URL is confirmed, research stays partial and drafting is blocked.

## Test

Set `SIGNAL_INTELLIGENCE_TEST_DATABASE_URL` to a disposable, migrated PostgreSQL database named exactly `signalscout_intelligence_test`, then run `python -m pytest -q tests`. Tests truncate only that explicitly named database. The pure core and CLI tests also run without Postgres; database tests skip when the test URL is absent. Provider calls are faked in tests.

## Acceptance limits

The agent suite passes against disposable PostgreSQL, and the independent UI/API run locally. A working Gemini key was exercised on a public PageBreak fixture for model chat, grounded research, and all four draft formats. Conversation merging and ranking are conservative heuristics; velocity may remain unknown with short history. Grounded search can return unrelated pages for ambiguous names, so full research requires confirmation from a starting source URL. Real company context and human editorial review remain pending. The main application integration is recorded separately in the [UI acceptance results](../../specs/features/intelligence-ui/acceptance_results.md). The [acceptance results](../../specs/features/intelligence-agent/acceptance_results.md) list exact evidence and open cases.

## Company knowledge retrieval

Apply application migrations through `0011_chunker_versions` using the pgvector-enabled PostgreSQL 17 image. Content/evidence mutations create durable indexing work in the same database. Main application workers index in small batches; standalone operators can run:

```sh
python tools/search_knowledge.py status
python tools/search_knowledge.py index
python tools/search_knowledge.py search "What have we said about retrieval quality?"
python tools/search_knowledge.py refine 1
```

The independent API exposes `/knowledge/status`, `/knowledge/index`, `/knowledge/search`, and `/opportunities/{id}/refine-angle`. Chat has the same search/refinement service tools. Main UI indexing/search/refinement is asynchronous through its existing queue. Company passages guide editorial history and voice; factual citations remain restricted to the selected completed research snapshot. Semantic indexing sends original text to Gemini; `KNOWLEDGE_SEMANTIC_ENABLED=false` retains lexical retrieval without embedding calls. Credentials stay outside browser responses/logs. See the [feature contract](../../specs/features/company-knowledge-rag/task_spec.md).

The application's Agent workspace uses `intelligence_workspace.py` for observable queued chat with the same `intelligence_chat.build_tools` service tools. It adds a stdlib REST model adapter to avoid adding the standalone SDK to the application lockfile. The original CLI/API/UI chat remains available. Main workspace activity records actual calls and named subprocess execution, not model reasoning.
