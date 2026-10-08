# Secure Agent

The notes agent from [`../example-agent/`](../example-agent/), hardened step by
step as in the course's security module. Same domain, same layers, same file
names, so you can compare the two folders file by file and see exactly what
securing an agent changes:

```bash
diff -ru example-agent/example_chat.py secure-agent/example_chat.py
```

| Step | What changed | Where | Proof |
|---|---|---|---|
| 1. Threat model and secrets | Threats ranked with a mitigation and a test each; env files read only from this folder | [`docs/threat-model.md`](docs/threat-model.md), `agent_env.py` | `test_env_files_are_read_only_from_the_agent_folder`, secrets audit in [`docs/learning-log.md`](docs/learning-log.md) |
| 2. Access tests | Every note, action and counter has an owner; API needs a bearer token; tools act as the session's user | `memory/memory.py`, `api/main.py`, `example_chat.build_tools` | [`tests/test_access.py`](tests/test_access.py) |
| 3. Injection and tool limits | No delete tool for the model; arguments validated in code; tool-call, time and daily caps; note text labelled as data | `example_chat.py`, `example_core.py` | [`tests/test_injection.py`](tests/test_injection.py), [`tests/test_limits.py`](tests/test_limits.py) |
| 4. Human approval | Deleting creates a pending action with a preview, digest and expiry; a person approves it outside the chat, once | `example_core.PendingAction`, `example_service.approve_action` | [`tests/test_approval.py`](tests/test_approval.py) |

`scripts/prove_guards.py` removes each of those checks in turn and confirms
the tests go red: a refusing test that also passes without its check proves
nothing.

## What the agent can and cannot do

| Action | Agent | Person |
|---|---|---|
| Search, list, summarize own notes | yes | yes |
| Add a note | yes | yes |
| Delete notes | **proposes** (`request_delete`) | approves or rejects; deletes own notes directly via the API |
| Touch another user's notes | no | no |

## Anatomy (differences from example-agent)

```
secure-agent/
├── example_core.py      # + owner on Note, input limits, PendingAction (preview, digest, expiry)
├── example_service.py   # every use case takes the user; request/approve/reject actions
├── example_chat.py      # tools bound to the user, no delete tool, budgets, notes_data label, model seam
├── example_agent.py     # CLI as one local user; asks y/N for each pending deletion
├── manage_users.py      # create API users; prints the token once
├── agent_env.py         # reads only this folder's .env files
├── agent_llm.py         # SECURE_AGENT_* settings, 30 s request timeout
├── memory/memory.py     # NoteStore, ActionStore, UsageStore, UserStore; locked atomic writes
├── subagents/           # summarizer requires --user and has no tools
├── api/main.py          # bearer auth on every data route, no CORS, /actions routes (port 8013)
├── docs/                # threat-model.md, learning-log.md
├── evals/               # example-agent's evals, adapted; hostile cases are the regression set
├── scripts/prove_guards.py
└── tests/
```

Removed on purpose: the Flask UI, the tool CLIs and the memory CLI. Each was
another way into the same data without authentication, and the agent's task
does not need them.

## Run

From `secure-agent/`, in a virtual environment:

```bash
python -m pip install -r requirements.txt
export SECURE_AGENT_OFFLINE=1                 # no model calls
export SECURE_AGENT_DATA_DIR="$(mktemp -d)"   # throwaway data
python -m pytest -q                           # 116 tests, offline
python scripts/prove_guards.py                # every check must report RED

# CLI as a local user
python example_agent.py --user alice --chat
#   You: add Old parking receipt
#   You: delete note_…           -> "Approve? Delete 1 note(s): 'Old parking receipt' [y/N]"

# API
python manage_users.py add alice              # prints alice's token once
python api/main.py                            # http://127.0.0.1:8013/docs
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8013/notes
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"digest": "<digest from the action>"}' http://127.0.0.1:8013/actions/<id>/approve
```

To use Gemini, put `GEMINI_API_KEY` in `secure-agent/.env.local` (only this
folder's env files are read) and unset `SECURE_AGENT_OFFLINE`.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` / `GOOGLE_AI_STUDIO_KEY` | — | Enables LLM mode |
| `SECURE_AGENT_OFFLINE` | — | `1` forces the offline router |
| `SECURE_AGENT_MODEL` | `gemini-3.8-flash` | Model for chat and summaries |
| `SECURE_AGENT_DATA_DIR` | `memory/data/` | Notes, actions, usage and users |
| `SECURE_AGENT_DAILY_MODEL_TURNS` | `100` | Model turns per user per day |
| `SECURE_AGENT_ACTION_TTL_SECONDS` | `900` | How long a pending deletion can be approved |
| `API_PORT` | `8013` | API port (always bound to 127.0.0.1) |

## Limits of this example

Tokens are long-lived bearer tokens stored as hashes. A real deployment
signs users in through an identity provider and keeps data in a database with
row-level security. See "Residual risks" in the threat model.
