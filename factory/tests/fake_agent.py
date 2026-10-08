#!/usr/bin/env python3
"""A stand-in for `claude -p` so the factory's gates can be tested for free.

run.sh calls it with FACTORY_BACKEND=fake. The stage comes from FACTORY_STAGE;
it behaves well unless FACTORY_FAKE_<STAGE>=<behaviour> asks it not to:

  spec:      good | missing | blocked | no_docs | touches_repo
  test:      edits_existing_on_review | good | touches_app | missing_test | passes_already
  implement: broken_on_fix |  good | touches_tests | touches_other | broken | leftover_names |
             parent_env | wide_bind | thin_readme |
             readme_provenance | code_hyphen_name
  review:    good | changes | changes_once | garbage
  implement: lazy_once | lazy_always (end the turn having changed nothing)
  any stage: expensive (reports a high cost) | rate_limit_once | rate_limit_always

It prints a result object shaped like Claude Code's `--output-format json`
and appends the stage to <run>/fake-calls.
"""

import json
import os
import re
import sys
from pathlib import Path

STAGE = os.environ["FACTORY_STAGE"]
RUN = Path(os.environ["FACTORY_RUN"])
BEHAVIOUR = os.environ.get(f"FACTORY_FAKE_{STAGE.upper()}", "good")
PROMPT = sys.argv[1]

issue = Path(re.search(r"^Issue file: (.+)$", PROMPT, re.M).group(1))
SLUG = re.search(r"^Agent: (\S+)", issue.read_text(), re.M).group(1)
SNAKE = SLUG.replace("-", "_")
ENVP = SNAKE.upper()
DIR = Path("agents") / SLUG
FEATURE = Path("specs/features") / SLUG
TEST_FILE = DIR / "tests" / "test_agent_contract.py"
TEST_NAME = "test_offline_env_is_agent_scoped"

TEST_BODY = f'''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def {TEST_NAME}():
    import {SNAKE}_core

    assert {SNAKE}_core.AGENT_NAME == "{SLUG}"
'''

PASSING_BODY = f"def {TEST_NAME}():\n    assert True\n"

README = f"""# {SLUG}

Purpose: a factory-built agent.

Offline: works without a provider key.

Memory retention: records stay in the local data directory until deleted.
"""


def spec_md() -> str:
    return (
        f"# 001 {SLUG}\n\n## Acceptance criteria\n\n"
        f"1. The core module names the agent {SLUG}.\n"
        f"2. The module {SNAKE}_core exists.\n\n"
        f"Test: {TEST_FILE}::{TEST_NAME}\n\n## Out of scope\n\nPublishing.\n"
    )


def adapt() -> None:
    """What a good implement pass does: the domain behaviour (the rename is the scaffold's job)."""
    core = DIR / f"{SNAKE}_core.py"
    core.write_text(core.read_text() + f'\nAGENT_NAME = "{SLUG}"\n')
    (DIR / "README.md").write_text(README)


def act() -> str:
    if STAGE == "spec":
        if BEHAVIOUR == "missing":
            return "I could not write the spec."
        if BEHAVIOUR == "blocked":
            (RUN / "spec.md").write_text("# 001\n\nBLOCKED: Should the agent publish posts?\n")
            return "Blocked."
        (RUN / "spec.md").write_text(spec_md())
        if BEHAVIOUR != "no_docs":
            FEATURE.mkdir(parents=True, exist_ok=True)
            for name in ("task_spec", "technical_spec", "test_plan"):
                (FEATURE / f"{name}.md").write_text(f"# {SLUG} {name}\n")
        if BEHAVIOUR == "touches_repo":
            Path("README.md").write_text("spec stage was here\n")
        return "Wrote the spec."

    if STAGE == "test" and re.search(r"Review round \d+", PROMPT):
        if BEHAVIOUR == "edits_existing_on_review":
            TEST_FILE.write_text(PASSING_BODY)   # rewrites (weakens) an existing test
        else:
            number = re.search(r"Review round (\d+)", PROMPT).group(1)
            (DIR / "tests" / f"test_review_round_{number}.py").write_text("def test_regression_for_review_finding():\n    assert True\n")
        return "Added tests for the findings."

    if STAGE == "test":
        if BEHAVIOUR != "missing_test":
            TEST_FILE.write_text(PASSING_BODY if BEHAVIOUR == "passes_already" else TEST_BODY)
        else:
            TEST_FILE.write_text("def test_something_else():\n    assert True\n")
        if BEHAVIOUR == "touches_app":
            (DIR / "agent_llm.py").write_text("# test stage was here\n")
        return "Wrote the test."

    if STAGE == "implement":
        adapt()
        if BEHAVIOUR == "broken_on_fix" and earlier > 0:
            (DIR / f"{SNAKE}_core.py").write_text("raise RuntimeError('broken by the fix')\n")
        if BEHAVIOUR == "broken":
            (DIR / f"{SNAKE}_core.py").write_text("raise RuntimeError('broken')\n")
        if BEHAVIOUR == "touches_tests":
            TEST_FILE.write_text(PASSING_BODY)
        if BEHAVIOUR == "touches_other":
            Path("README.md").write_text("implement stage was here\n")
        if BEHAVIOUR == "leftover_names":
            (DIR / "notes.txt").write_text("see example_agent for details\n")
        if BEHAVIOUR == "parent_env":
            (DIR / "agent_env.py").write_text("for d in [AGENT_DIR, *AGENT_DIR.parents]:\n    pass\n")
        if BEHAVIOUR == "wide_bind":
            (DIR / "serve.py").write_text('HOST = "0.0.0.0"\n')
        if BEHAVIOUR == "readme_provenance":
            (DIR / "README.md").write_text(README + "\nBuilt from `../example-agent/` following ../AGENTS.md.\n")
        if BEHAVIOUR == "code_hyphen_name":
            (DIR / "banner.py").write_text('BANNER = "copied from example-agent"\n')
        if BEHAVIOUR == "thin_readme":
            (DIR / "README.md").write_text(f"# {SLUG}\n")
        return "Implemented."

    if STAGE == "review":
        if BEHAVIOUR == "garbage":
            return "Looks fine to me!"
        if BEHAVIOUR == "changes_once" and earlier == 0:
            return json.dumps({"verdict": "changes", "findings": ["Negative limit drops items."]})
        if BEHAVIOUR == "changes":
            return json.dumps({"verdict": "changes", "findings": ["The README omits setup."]})
        return json.dumps({"verdict": "approve", "findings": []})
    raise SystemExit(f"unknown stage {STAGE}")


with open(RUN / "fake-calls", "a") as calls:
    calls.write(STAGE + "\n")
with open(RUN / "fake-prompts", "a") as prompts:
    prompts.write(PROMPT + "\n=====\n")
earlier = (RUN / "fake-calls").read_text().split().count(STAGE) - 1
if STAGE == "implement" and (BEHAVIOUR == "lazy_always" or (BEHAVIOUR == "lazy_once" and earlier == 0)):
    print(json.dumps({"subtype": "success", "is_error": False, "result": "Now the README, init files...",
                      "num_turns": 30, "total_cost_usd": 0.01}))
    raise SystemExit(0)
if BEHAVIOUR == "rate_limit_always" or (BEHAVIOUR == "rate_limit_once" and earlier == 0):
    if STAGE == "implement":  # partial work that must not survive the retry
        (DIR / "half-done.txt").write_text("partial\n")
    print(json.dumps({"subtype": "error", "is_error": True, "num_turns": 9, "total_cost_usd": 0.01,
                      "result": "Tokens per minute limit exceeded - too many tokens processed."}))
    raise SystemExit(0)
result = act()
cost = 50.0 if BEHAVIOUR == "expensive" or os.environ.get("FACTORY_FAKE_EXPENSIVE") == STAGE else 0.01
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result,
                  "num_turns": 3, "total_cost_usd": cost, "modelUsage": {"fake-model": {}}}))
