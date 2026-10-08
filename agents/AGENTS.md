# Agent development workflow

This repository is the agent kit. Put each agent in `<agent-name>/` at this
root. Use
[`example-agent/`](example-agent/) as the full reference: it has chat, offline
behavior, a service layer, tools, skills, local memory, a subagent, CLI, API,
UI, and tests. `gemini_agent.py` is an optional standalone model-client example.

## Architecture to carry across

The reference's dependencies have one direction:

```text
CLI / API / UI chat ──> chat ──> service ──> pure core
                         │         ├──────> memory
                         │         └──────> subagent process
                         └── model-callable wrappers around service functions
Tool CLIs ─────────────────────────> service
```

- Keep domain rules and calculations in a pure, tested core module. The service
  combines those rules with persistence and owns use cases.
- Make chat call the service through bounded, documented model tools. Provide
  an offline path that works without a provider key. In `example-agent`, skill
  Markdown is loaded into the model system prompt; the offline router uses code.
- Give each standalone tool and subagent a clear job and a JSON stdout
  contract. The reference uses `agent_cli.py` for success/error envelopes and
  launches subagents as separate processes with a timeout and shared data-dir
  setting. The main chat CLI prints conversational text, not that JSON envelope.
- Define memory records, storage location, and retention before persisting
  data. Keep live records out of the reference folder and copied source.
- Expose only the interfaces the new agent needs. Direct API/UI routes, tool
  CLIs, and chat tools should reach the same service use cases.

## Build a new agent

1. **Copy safely.** Follow the command in [README.md](README.md#copy-the-full-example).
   It excludes the reference's existing notes, local env files, and generated
   Python files.
2. **Write the contract.** In the new agent's README, state its purpose,
   inputs, outputs, permissions, side effects, offline behavior, memory
   retention, and chosen CLI/API/UI surfaces. Rename `example_*` modules and
   `EXAMPLE_AGENT_*` settings to match the new agent. Review environment loading
   so the copy cannot pick up unrelated parent-project credentials.
3. **Implement core and memory with TDD.** Write a failing test for each next
   observable behavior, confirm the failure, implement it, then refactor while
   green. Replace the note model, schema, and store with domain-specific data.
   Tests must use a disposable data directory and no real provider calls.
4. **Build the service and capabilities.** Put use cases in the service layer.
   Add tool CLIs for distinct actions, skill Markdown for their usage, and a
   subagent process only for a self-contained delegated job. Test their public
   JSON and error contracts.
5. **Wire chat and interfaces.** Map model-callable functions and the offline
   router to the same service actions. Then adapt the main CLI, API routes, and
   UI. Check that history, errors, and state agree across the chosen surfaces.
6. **Verify the full path.** Run offline tests and a CLI/tool/API integration
   path with isolated data. If there is a UI, exercise its main flows and chat
   in a real browser. Browser tests may be optional in the normal test run,
   but an actual browser check is required before acceptance.
7. **Register and document.** Add the agent to the table below. Update its
   README with setup, environment, run, test, and safe copy instructions.

## Naming and local safety

- Use kebab case for folders and skill files; use snake case for Python
  modules, JSON schemas, and environment prefixes.
- Put no secrets in `.env.example`. Keep `.env`, `.env.local`, keys,
  local memory data, caches, and virtual environments out of copied code and
  version control. Review a copied agent before sharing it.
- The reference API and UI have no authentication. They bind to `127.0.0.1`
  for local development. Network or multi-user access needs an explicit
  authentication, authorization, origin, and deployment design.
- Keep provider failures from breaking offline behavior. Do not treat model
  output as a source of deterministic facts or persisted records without
  validation.

## Registered agents

| Agent | Role | Status |
|---|---|---|
| [`example-agent/`](example-agent/) | Complete notes-based process reference, with an eval set in `evals/` | Reference |
| [`secure-agent/`](secure-agent/) | The same notes agent hardened: per-user access, no model-callable delete, tool limits, human approval, threat model | Reference (security) |
| [`signal-intelligence/`](https://github.com/ModernPath/signal-scout/tree/main/agents/signal-intelligence) | Phase 2 conversation, ranking, research, and drafting agent using application PostgreSQL (lives in the SignalScout repository) | Independent architecture and main application integration built; company editorial acceptance pending |
| [`reading-list/`](reading-list/) | Saves articles to a local reading list, tags and ranks them by interest | Factory draft; pending human review |

The per-agent [reference README](example-agent/README.md) gives file-by-file
anatomy, commands, environment variables, and implementation details.
