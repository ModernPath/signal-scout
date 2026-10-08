# Agents

Start with [`example-agent/`](example-agent/) when building a full agent. Its
notes domain is small, but it demonstrates chat, offline behavior, shared
service functions, tools, skills, memory, a subagent, CLI, API, UI, and tests.
The [agent workflow](AGENTS.md) explains how to adapt and verify those parts.

`gemini_agent.py` is a separate optional model-client example.

Two teaching additions build on the same notes agent:

- [`example-agent/evals/`](example-agent/evals/README.md) measures the agent:
  22 cases with expected evidence, a runner with repeated trials, exact
  graders, an LLM judge with calibration against your own labels, and a model
  comparison on quality, cost and p90 latency.
- [`secure-agent/`](secure-agent/README.md) is the agent hardened:
  a threat model, per-user access with tests, no delete tool for the model,
  tool and spend limits, and human approval for deletions. Compare it with
  `example-agent/` file by file.

[`signal-intelligence/`](https://github.com/ModernPath/signal-scout/tree/main/agents/signal-intelligence) is the standalone Phase 2 SignalScout
agent, kept in the SignalScout repository. It uses the application's PostgreSQL database and
application-owned migrations. See its README for setup, commands, and current acceptance gaps.

## Try the full example

From the repository root:

```bash
cd example-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
export EXAMPLE_AGENT_OFFLINE=1
export EXAMPLE_AGENT_DATA_DIR="$(mktemp -d)"
python -m pytest -q
python example_agent.py --chat
```

The chat CLI accepts commands such as `add Buy oat milk #shopping`,
`list notes`, and `summarize`. It works without a model key. In separate
terminals with the same offline and data-dir settings, run `python api/main.py`
for the API at `http://127.0.0.1:8012/docs` and `python ui/app.py` for the UI at
`http://127.0.0.1:5012/`; its chat is at `/chat`. Both servers bind to
loopback for local development and have no authentication.

The [example README](example-agent/README.md#run) has the tool, subagent,
memory, environment, and browser-test commands. Its existing notes are example
state, so use a disposable data directory when exploring or testing.

## Copy the full example

From this repository root, replace `my-agent` with a kebab-case name:

```bash
rsync -a \
  --exclude '/memory/data/*' \
  --exclude '.env' --exclude '.env.local' --exclude '.venv/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest_cache/' \
  example-agent/ my-agent/
mkdir -p my-agent/memory/data
touch my-agent/memory/data/.gitkeep
```

This leaves behind `example-agent/memory/data/notes.json` and local secrets.
Complete the [build sequence](AGENTS.md#build-a-new-agent), then update the
copied README, module names, environment prefix, tests, and registration.
Use only a data directory and provider credentials that belong to the new
agent. The root and copied `.env.example` files contain commented variable
names; uncomment and set values in an ignored `.env.local` only when needed.
