# Example Agent

A complete reference agent for the process in [`../AGENTS.md`](../AGENTS.md).
Its domain is deliberately small (personal notes), so the structure is what you
learn. Use the [safe copy command](../README.md#copy-the-full-example) when
starting a new agent; the existing `memory/data/notes.json` is example state and
must not be copied.

## Anatomy

```
example-agent/
├── example_agent.py        # CLI entry point: --chat, single query, --offline
├── example_core.py         # Pure domain logic: Note model, tags, search, offline summary
├── example_service.py      # Use cases shared by every interface + subagent delegation
├── example_chat.py         # Chat: Gemini function calling, or an offline command router
├── agent_env.py            # Loads .env / .env.local from this folder upwards
├── agent_llm.py            # Gemini client, API key lookup, offline switch
├── agent_cli.py            # JSON envelope used by every tool/subagent/memory CLI
├── .env.example            # Commented, non-secret environment options
├── memory/
│   ├── memory.py           # NoteStore (JSON file, atomic writes) + inspection CLI
│   ├── note_schema.json    # Data schema
│   └── data/               # notes.json lives here (gitignored)
├── tools/                  # One CLI per action the agent can take
│   ├── add_note.py
│   ├── search_notes.py
│   └── delete_note.py
├── subagents/
│   └── note_summarizer.py  # Independent process with one job, run by the service layer
├── skills/                 # Markdown loaded into the system prompt
├── api/main.py             # FastAPI REST API   (port 8012)
├── ui/app.py               # Flask web UI       (port 5012)
└── tests/                  # pytest: core, memory, service, chat, API, UI, CLIs, browser
```

### How the layers connect

```
 CLI ─┐
 API ─┼──► example_chat ──► example_service ──► example_core   (pure logic)
 UI  ─┤        │                   │
tools ┘   Gemini tools        memory.NoteStore                  (persistence)
                                   │
                        subagents/note_summarizer.py            (separate process)
```

- **Dependencies point one way.** `example_core` imports nothing from the agent.
  The service layer combines core and memory. Tool CLIs and direct API/UI routes
  call the service; conversational entry points call `example_chat`, whose
  tools also call the service.
- **The LLM uses the same functions as everything else.** `example_chat.build_tools()` wraps
  service functions as plain Python callables. google-genai turns their signatures and docstrings
  into function declarations and runs the tool loop for you (automatic function calling).
- **Offline mode always works.** With no API key, with `--offline`, with `EXAMPLE_AGENT_OFFLINE=1`,
  or if the LLM call fails, a small regex router handles `add …`, `find …`, `list notes`,
  `delete note_…` and `summarize`.
- **Subagents are processes, not imports.** `example_service.run_subagent()` runs
  `subagents/<name>.py`, passes the data dir through the environment, and reads the JSON output.
- **One error vocabulary.** `ValueError` means bad input (HTTP 400), `LookupError`/`NotFoundError`
  means missing (HTTP 404), and `SubagentError` means the delegate failed (HTTP 502). CLIs print
  `{"status": "error", "error": …}` and exit with code 1.

## Run

Run these commands from `example-agent/`, preferably in a virtual
environment. Set `EXAMPLE_AGENT_OFFLINE=1` for a demo that never calls Gemini,
and set `EXAMPLE_AGENT_DATA_DIR` to a fresh directory to leave the reference
notes untouched. Use separate terminals for the API and UI, carrying those
settings into each. Both development servers bind to `127.0.0.1` and have no
authentication; do not expose them on a network without an access design.

```bash
python -m pip install -r requirements.txt

# CLI
python example_agent.py --chat
python example_agent.py "remember to call Bob about the renewal #work"
python example_agent.py --offline "list notes"

# Tools, subagent, memory (each prints one JSON object)
python tools/add_note.py --title "Call Bob" --tags "work, sales"
python tools/search_notes.py --query bob
python subagents/note_summarizer.py --tag work
python memory/memory.py stats

# API → http://127.0.0.1:8012/docs
python api/main.py

# UI → http://127.0.0.1:5012/ (chat at /chat)
python ui/app.py
```

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` / `GOOGLE_AI_STUDIO_KEY` | Enables LLM mode (otherwise offline) |
| `EXAMPLE_AGENT_OFFLINE=1` | Force offline mode even when a key is set |
| `EXAMPLE_AGENT_MODEL` | Override the model (default `gemini-3.8-flash`) |
| `EXAMPLE_AGENT_DATA_DIR` | Store notes somewhere other than `memory/data/` |
| `PORT` / `API_PORT` | UI / API port |
| `FLASK_SECRET` | Set a private session secret before using the UI beyond disposable local development |

Copy `.env.example` to `.env.local` for optional settings. `.env.local` is
ignored; never place real keys or private notes in the copied reference files.

## Test

```bash
python -m playwright install chromium   # once, after installing requirements
python -m pytest -q                   # offline, temp data; includes browser journeys
```

## Turn this into your own agent

1. Follow the [safe copy command](../README.md#copy-the-full-example), then
   rename `example_*` files and the `EXAMPLE_AGENT_*` variables.
2. Replace `example_core.py` with your domain model and rules. Keep it pure.
3. Update `memory/memory.py` and the `*_schema.json` files for your data.
4. Rewrite `example_service.py` use cases. Direct routes, tool CLIs, and chat
   wrappers should reach these same actions.
5. Update `build_tools()` in the chat module. The docstrings are what the LLM reads.
6. Add a CLI per tool in `tools/`, one skill `.md` per capability, and subagents for
   self-contained subtasks.
7. Adjust the CLI, API routes, and UI templates. Keep chat, direct routes, and
   tools on the same service contract.
8. Run isolated offline tests and the main UI path in a browser, then register
   the agent in `../AGENTS.md`.

## Gotchas learned building this

- **No `from __future__ import annotations` in the module that defines Gemini tools.**
  google-genai validates arguments with `isinstance(value, annotation)`, so string annotations
  make every tool call with arguments fail. `tests/test_chat.py` guards against this.
- **Keep a reference to the `genai.Client` while you use it.** The SDK closes its HTTP connection
  when the client is garbage-collected, so `get_client().chats.create(...).send_message(...)`
  can fail with "client has been closed".
