# Agent factory — test plan

**Behavior:** [Task spec](task_spec.md)

All cases run `factory/tests/test_factory.py` with `FACTORY_BACKEND=fake` (no model, no network).

| Case | Scenario | Expected result |
|---|---|---|
| F-01 | Well-behaved fake agent | State: spec, scaffold, test, red, implement, register, review, pr; `pr.md`; back on main; main unchanged |
| F-02 | Scaffold content | No `tests/`, `.env*`, caches, or notes data copied; `memory/data/.gitkeep` present |
| F-03 | Spec stage writes no feature docs / touches other files / is BLOCKED | Stop at spec |
| F-04 | Test stage edits outside `tests/`, omits the named test | Stop at test |
| F-05 | New test already passes | Stop at RED gate |
| F-06 | Implement edits tests or files outside the agent folder | Stop at implement scope gate |
| F-07 | Implementation leaves tests failing | Stop at GREEN gate |
| F-08 | Leftover `EXAMPLE_AGENT`; parent-dir env loading; `0.0.0.0`; README missing retention | Stop at hygiene gate |
| F-09 | Reviewer asks for changes / returns non-JSON | Stop at verdict gate |
| F-10 | Over-budget stage | Stop with budget reason |
| F-11 | Bad agent name; agent folder already exists | Refused before any branch is made |
| F-12 | Pre-existing untracked file in the repo, then a stop | File still present afterwards |
| F-13 | Rerun after a stop | Finished stages are skipped |

**Exit criteria:** all cases pass; one real run on a small brief is reviewed by a person before the factory is trusted (not yet done).
