# Agent factory — task spec

**Technical design:** [Technical spec](technical_spec.md)
**Verification:** [Test plan](test_plan.md)
**Derived from:** `factory-example/` (the course's software-factory example)
**Status:** Built; gates proven against a fake agent. A real `claude -p` run on `briefs/001-reading-list.md` is in progress; see acceptance results when written.

## Outcome

From the repository root, `bash factory/run.sh factory/briefs/<nnn>-<slug>.md` turns one agent brief into a reviewed **draft** change on a `factory/<run id>` branch: a new `agents/<slug>/` copied from `agents/example-agent/`, built following [`agents/AGENTS.md`](../../../agents/AGENTS.md), with feature specs in `specs/features/<slug>/`. A person decides whether to merge.

## In scope

- Task class: create one new agent folder under `agents/` from a brief (purpose, inputs, outputs, permissions, side effects, offline behavior, memory retention, surfaces, out of scope).
- Stages: spec, scaffold (script), test, implement, review, PR text. Machine gates between stages.
- Safe copy of the reference agent exactly as `agents/README.md` prescribes.
- Registration row in `agents/AGENTS.md` after the suite is green.
- Stop reports (`stop.md`) naming the failed gate and the decision a person must make.

## Boundaries

The factory never merges, never changes `factory/`, `src/`, `migrations/`, `agents/example-agent/` or `agents/signal-intelligence/`, never touches secrets or `.env*`, and cannot perform the required real-browser check of a UI. It cannot judge editorial quality.

## Acceptance criteria

1. A good run produces `specs/features/<slug>/{task_spec,technical_spec,test_plan}.md`, a scaffold commit, one test commit, an implement commit, a registration commit and `pr.md`, all on `factory/<run id>`, and returns to the starting branch with `main` unchanged.
2. The scaffold excludes the reference's notes, local env files, caches, virtualenvs and tests.
3. RED gate: the suite must fail, and the failure must name a new test file, before implementation.
4. Scope gates: the spec stage changes only `specs/features/<slug>/`; the test stage only adds files in `agents/<slug>/tests/`; the implement stage only `agents/<slug>/` outside `tests/`.
5. GREEN gate: the offline suite passes with provider keys removed from the environment.
6. Hygiene gate rejects: leftover `example_*`/`EXAMPLE_AGENT` names, `agent_env.py` reading parent directories, binds to `0.0.0.0`, tracked `.env*` or live `memory/data` records, and a README lacking purpose, offline and retention.
7. Review gate: only a read-only reviewer's JSON `approve` lets the run finish.
8. Any failed gate, timeout or budget exhaustion writes `stop.md`, restores the starting branch and leaves the user's own untracked files and `main` untouched.
9. Review findings are fixed and re-reviewed for a bounded number of rounds; findings that persist stop the run for a person.
10. A rerun of the same command resumes after the last finished stage.
