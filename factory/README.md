# Agent factory

Turns one **agent brief** into a reviewed **draft change** that adds a new agent
to [`agents/`](../agents/): a copy of [`agents/example-agent/`](../agents/example-agent/)
adapted by headless coding agents following [`agents/AGENTS.md`](../agents/AGENTS.md),
with feature specs in `specs/features/<agent>/`. Between stages the script runs
gates that no model can talk its way past, and stops with a report when one fails.
Derived from `factory-example/`; design in [`specs/features/agent-factory/`](../specs/features/agent-factory/).

```
factory/briefs/001-<slug>.md
   │
   ▼  spec       (writes specs/features/<slug>/ + run spec.md)  → spec gate
   ▼  scaffold   (script: the copy command from agents/README.md, plus the renames)
   ▼  test       (adds agents/<slug>/tests/ only)               → test gate, RED gate
   ▼  implement  (adapts agents/<slug>/, never its tests)       → scope, GREEN, hygiene gates
   ▼  register   (script: one row in agents/AGENTS.md)
   ▼  review     (read-only, fresh context)                     → verdict gate
        └─ findings → another implement pass → gates → re-review (bounded rounds)
   ▼  draft PR text (the script) — a person decides whether to merge
```

## Run it from the repository root

You need `git`, `rsync`, Python 3.9+ with the agent's requirements
(`agents/example-agent/requirements.txt`), and `claude`, `codex` or `opencode` signed in. No API key is needed.

```bash
python3 -m venv .venv-agents && .venv-agents/bin/pip install -r agents/example-agent/requirements.txt
export FACTORY_PYTHON=$PWD/.venv-agents/bin/python        # interpreter used by the gates

cp factory/briefs/_template.md factory/briefs/002-my-agent.md   # fill it in, commit it
bash factory/run.sh factory/briefs/001-reading-list.md          # the sample brief
cat factory/runs/001-reading-list/log
```

The working tree's tracked files must be clean (your untracked files are left alone).
The run works on `factory/<run id>`, returns you to your branch, and writes
everything to `factory/runs/<run id>/`: log, state, each stage's output, `spec.md`,
`red.txt`, `green.txt`, `diff.patch`, `review.json`, and `pr.md` or `stop.md`.
Rerun the same command after a stop or Ctrl-C: finished stages are skipped.

### Backends

| `FACTORY_BACKEND` | Stage permissions | Turn / budget caps |
|---|---|---|
| `claude` (default) | `--allowedTools` per stage | yes |
| `codex` | sandbox `read-only` / `workspace-write` only | no |
| `opencode` | deny-by-default `permission` config generated per stage from the same tool list; empty `XDG_CONFIG_HOME` and `--pure` keep your personal config, MCP servers and plugins out | no: only the stage timeout |

For opencode set `FACTORY_MODEL=<provider>/<model>` (see `opencode models`), e.g.
`FACTORY_BACKEND=opencode FACTORY_MODEL=opencode/big-pickle bash factory/run.sh factory/briefs/001-reading-list.md`.
Without a turn cap and budget, `FACTORY_MAX_COST_USD` only blocks the next stage once a finished one has overspent; the gates are unchanged.

Settings are listed at the top of [`run.sh`](run.sh): `FACTORY_BACKEND=codex`,
`FACTORY_PR=gh`, `FACTORY_RUN_ID`, `FACTORY_MODEL`, `FACTORY_MAX_COST_USD`,
`FACTORY_STAGE_TIMEOUT`, `FACTORY_MAX_TURNS`, `FACTORY_IMPLEMENT_PASSES` (8), `FACTORY_REVIEW_ROUNDS` (2), `FACTORY_RETRIES`/`FACTORY_RETRY_WAIT` (provider rate limits).

## Brief format

See [`briefs/_template.md`](briefs/_template.md). `Agent:` (kebab case, must not
already exist in `agents/`) and `Role:` are required; the rest becomes the
agent's contract. Test a brief by asking whether a new developer could build the
agent from it and the repository alone — a factory agent cannot ask questions.

## What each stage may change

| Stage | Agent permissions (Claude) | May change | Gate after it |
|---|---|---|---|
| spec | Read, Grep, Glob, Write | `specs/features/<slug>/`, run `spec.md` | three docs exist; numbered criteria; named tests; nothing else changed |
| scaffold | script | `agents/<slug>/`: copy without tests/evals/notes/env/caches, then modules, settings, names, entry point and `agent_env.py` renamed and confined to the agent folder | — |
| test | Read, Grep, Glob, Edit, Write | new files in `agents/<slug>/tests/` | every named test exists; no existing file edited |
| (RED) | — | — | suite **fails**, in the new tests |
| implement | + `check.sh`, `git mv`, `git rm` | `agents/<slug>/` except `tests/` | nothing else changed; suite **passes** offline; hygiene. Up to 8 passes, each told the failing output and a test file to focus on |
| register | script | one row in `agents/AGENTS.md` | — |
| review | Read, Grep, Glob | nothing | valid JSON, `approve` |

Hygiene gate: no `example_agent`/`EXAMPLE_AGENT`/`example_core` left (and no `example-agent` in code; a README may link to its source); `agent_env.py`
does not read parent directories (the root `.env` holds credentials); no `0.0.0.0`;
no `.env`, `.venv` or live `memory/data`; README states purpose, offline behavior and retention.

## Never changed by the factory

`factory/`, `agents/example-agent/`, `agents/signal-intelligence/`, `src/`, `migrations/`,
CI, dependencies, secrets and `.env*`, the main branch. A person merges.

## Prove the gates

```bash
python3 -m pytest -q factory/tests    # each gate fires against a misbehaving fake agent; free
```

Policy for unattended use: [`decisions.md`](decisions.md). A real run on the sample brief with `claude` got through every stage; see
the feature's task spec for status. The `opencode` + Cerebras path stalled on
per-minute token limits (see `specs/features/agent-factory/technical_spec.md`).
