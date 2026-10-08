# Agent factory — technical spec

**Behavior:** [Task spec](task_spec.md)

## Layout (repository root)

| Path | Purpose |
|---|---|
| `factory/run.sh` | Pipeline, gates, state file, budgets, stop report, PR text |
| `factory/check.sh` | The one test command: offline, provider keys unset, scoped to `agents/<slug>` |
| `factory/prompts/{spec,test,implement,review}.md` | One versioned prompt per agent stage |
| `factory/briefs/` | Briefs (`_template.md`, numbered briefs) |
| `factory/tests/` | Gate tests against a fake agent |
| `factory/runs/<run id>/` | Local run state (gitignored) |
| `factory/decisions.md` | Operating policy |

## Decisions

- **Scaffold is a script step, not an agent step.** The copy command in `agents/README.md` is deterministic; a model adds nothing but risk. The agent renames modules afterwards.
- **Tests are written against a copy that still has `example_*` names.** The first failure is therefore real (missing modules, wrong env prefix), which makes the RED gate meaningful.
- **Pathspec-limited git operations.** The repository holds unrelated untracked work. At start the script records `git ls-files --others` as a baseline; gates and cleanup act only on changes beyond it, so a stop never removes the user's files.
- **Same gate semantics as `factory-example`**: state file, set-aside patches, timeouts, `--setting-sources project`, `--strict-mcp-config`, no skip-permissions flags.
- **Larger defaults than the example** because an agent is bigger than a validation rule: 60 turns, 1800 s per stage, \$15 per run.
- **Naming**: slug = kebab case; module prefix = snake case; env prefix = upper snake. `<ENV>_OFFLINE` and `<ENV>_DATA_DIR` follow the reference.
- **Hygiene gate** encodes the `agents/AGENTS.md` safety rules mechanically, notably that `agent_env.py` must not load `.env` files from parent directories (the repository root `.env` holds real credentials).

- **Backends**: `claude`, `codex`, `opencode`. For opencode, `factory/opencode_permissions.py` converts a stage's tool list into a deny-by-default `permission` config (verified against opencode 1.18.34: denied bash commands are refused, allowed ones and edits work) and `factory/opencode_result.py` converts its JSON event stream into the `claude -p` result shape, treating an error event, non-zero exit or unfinished stream as failure. opencode has no turn or budget flag.

- **Mechanical work is the script's, domain work is the model's.** The scaffold renames modules, the entry point, settings, titles and confines `agent_env.py`; this was found necessary when a weak model burned its token quota reading the whole reference before making an edit. Implement then runs in bounded passes with a fresh context, the failing output and one test file to focus on.
- **Review findings are acted on, boundedly.** On `changes` the findings go to an implement pass (tests stay frozen), gates re-run, and the change is re-reviewed, up to `FACTORY_REVIEW_ROUNDS`. A stop still needs a person.
- **Provider rate limits** (`FACTORY_RETRIES`) wait and retry a stage from a clean tree.
- **Trial findings (Cerebras `qwen-3.8-27b`)**: the key allowed 150k uncached and 750k total tokens/min; the implement stage exceeded both. `gpt-oss-120b` has 3x the headroom. With `claude -p` all stages ran.

## Not covered

UI browser acceptance, editorial review, provider-backed behavior, and CI. The PR text lists these as person-owned.
