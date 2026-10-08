"""The factory's gates, tested against a fake agent.

Each test copies the reference agent, the agents registry and the factory into
a fresh git repository and runs `bash factory/run.sh` with FACTORY_BACKEND=fake.
The fake agent behaves well unless a test asks one stage to misbehave; the test
then checks that the right gate stopped the run, that stop.md says why, and that
nothing reached main. A gate proves itself only by being seen to fire.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FAKE_AGENT = REPO / "factory" / "tests" / "fake_agent.py"
BRIEF = "factory/briefs/001-demo-scout.md"
RUN_ID = "001-demo-scout"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "runs", ".venv", "*.pyc")

BRIEF_TEXT = """# 001 Demo scout
Agent: demo-scout
Role: Demonstration agent built by the factory
Purpose: Prove the pipeline.
Surfaces: cli
Out of scope: publishing
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "agents").mkdir(parents=True)
    for name in ("AGENTS.md", "README.md", ".gitignore"):
        shutil.copy(REPO / "agents" / name, root / "agents" / name)
    shutil.copytree(REPO / "agents" / "example-agent", root / "agents" / "example-agent", ignore=IGNORE)
    shutil.copytree(REPO / "factory", root / "factory", ignore=IGNORE)
    (root / "specs" / "features").mkdir(parents=True)
    (root / ".gitignore").write_text("factory/runs/\n__pycache__/\n*.pyc\n.pytest_cache/\n.env\n.env.*\n!.env.example\n")
    (root / "factory" / "briefs" / "001-demo-scout.md").write_text(BRIEF_TEXT)
    (root / "agents" / "example-agent" / "evals").mkdir(exist_ok=True)
    (root / "agents" / "example-agent" / "evals" / "cases.json").write_text("[]")
    (root / "agents" / "example-agent" / "memory" / "data").mkdir(parents=True, exist_ok=True)
    (root / "agents" / "example-agent" / "memory" / "data" / "notes.json").write_text('["private note"]')
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "factory@example.invalid")
    git(root, "config", "user.name", "Factory Test")
    git(root, "add", "-A", "-f", "agents/example-agent/memory/data/notes.json")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "initial")
    return root


def run(project: Path, brief: str = BRIEF, **fake: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "FACTORY_BACKEND": "fake", "FACTORY_FAKE_AGENT": str(FAKE_AGENT),
           "FACTORY_PYTHON": sys.executable, "FACTORY_IMPLEMENT_PASSES": "1", "FACTORY_REVIEW_ROUNDS": "0"}
    for key, value in fake.items():
        env[key if key.startswith("FACTORY_") else f"FACTORY_FAKE_{key.upper()}"] = value
    return subprocess.run(["bash", "factory/run.sh", brief], cwd=project, env=env,
                          capture_output=True, text=True, timeout=300)


def run_dir(project: Path, run_id: str = RUN_ID) -> Path:
    return project / "factory" / "runs" / run_id


def states(project: Path, run_id: str = RUN_ID) -> list:
    path = run_dir(project, run_id) / "state"
    return [line.split()[0] for line in path.read_text().splitlines()] if path.exists() else []


def calls(project: Path, run_id: str = RUN_ID) -> list:
    path = run_dir(project, run_id) / "fake-calls"
    return path.read_text().split() if path.exists() else []


def assert_stopped(proc, project: Path, stage: str, reason: str, run_id: str = RUN_ID) -> str:
    assert proc.returncode == 1, proc.stdout + proc.stderr
    stop = (run_dir(project, run_id) / "stop.md").read_text()
    assert f"stage={stage}" in stop and reason in stop, stop
    assert "Decision needed:" in stop
    # Nothing follows the person back: we are on main, main is untouched, tracked files are clean.
    assert git(project, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git(project, "log", "--oneline", "main").count("\n") == 0
    assert git(project, "status", "--porcelain", "--untracked-files=no") == ""
    return stop


class TestHappyPath:
    def test_brief_becomes_a_reviewed_agent_with_pr_text(self, project):
        proc = run(project)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert calls(project) == ["spec", "test", "implement", "review"]
        assert states(project) == ["spec", "scaffold", "test", "red", "implement", "register", "review", "pr"]
        assert git(project, "rev-parse", "--abbrev-ref", "HEAD") == "main"
        assert git(project, "log", "--oneline", "main").count("\n") == 0
        pr = (run_dir(project) / "pr.md").read_text()
        assert "Draft" in pr and "RED" in pr and "GREEN" in pr and "browser" in pr.lower()
        git(project, "switch", "-q", "factory/" + RUN_ID)
        assert (project / "agents" / "demo-scout" / "demo_scout_core.py").exists()
        assert not (project / "agents" / "demo-scout" / "example_core.py").exists()
        for doc in ("task_spec", "technical_spec", "test_plan"):
            assert (project / "specs" / "features" / "demo-scout" / f"{doc}.md").exists()
        registry = (project / "agents" / "AGENTS.md").read_text()
        assert "[`demo-scout/`](demo-scout/)" in registry and "Demonstration agent" in registry
        assert len([s for s in git(project, "log", "--format=%s", "main..HEAD").splitlines()]) == 5

    def test_scaffold_leaves_private_and_generated_files_behind(self, project):
        run(project)
        git(project, "switch", "-q", "factory/" + RUN_ID)
        new = project / "agents" / "demo-scout"
        assert not (new / "memory" / "data" / "notes.json").exists()
        assert (new / "memory" / "data" / ".gitkeep").exists()
        assert not (new / "evals").exists()
        assert not any(f.name.startswith("example_") for f in new.rglob("*.py"))   # the reference's eval set is not part of a new agent
        assert not list(new.rglob("__pycache__"))
        assert not (new / ".env").exists()
        assert (project / "agents" / "example-agent" / "memory" / "data" / "notes.json").exists()

    def test_rerun_skips_finished_stages(self, project):
        assert run(project, FACTORY_FAKE_IMPLEMENT="broken").returncode == 1
        assert states(project) == ["spec", "scaffold", "test", "red"]
        proc = run(project)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert calls(project) == ["spec", "test", "implement", "implement", "review"]


class TestBriefChecks:
    def test_bad_agent_name_is_refused_before_any_branch(self, project):
        bad = project / "factory" / "briefs" / "002-bad.md"
        bad.write_text("# 002 Bad\nAgent: Bad_Name\nRole: x\n")
        git(project, "add", "-A"); git(project, "commit", "-q", "-m", "brief")
        proc = run(project, "factory/briefs/002-bad.md")
        assert proc.returncode == 2 and "kebab" in proc.stderr
        assert git(project, "branch", "--list", "factory/*") == ""

    def test_existing_agent_folder_is_refused(self, project):
        brief = project / "factory" / "briefs" / "003-clash.md"
        brief.write_text("# 003 Clash\nAgent: example-agent\nRole: x\n")
        git(project, "add", "-A"); git(project, "commit", "-q", "-m", "brief")
        proc = run(project, "factory/briefs/003-clash.md")
        assert proc.returncode == 2 and "already exists" in proc.stderr

    def test_dirty_tracked_tree_is_refused(self, project):
        (project / "agents" / "README.md").write_text("edited\n")
        proc = run(project)
        assert proc.returncode == 2 and "uncommitted" in proc.stderr


class TestSpecGates:
    def test_missing_spec_stops(self, project):
        assert_stopped(run(project, spec="missing"), project, "spec", "spec.md is missing")

    def test_blocked_spec_stops_with_the_question(self, project):
        assert_stopped(run(project, spec="blocked"), project, "spec", "Should the agent publish posts?")

    def test_missing_feature_docs_stop(self, project):
        assert_stopped(run(project, spec="no_docs"), project, "spec", "task_spec.md")

    def test_spec_touching_other_files_stops(self, project):
        assert_stopped(run(project, spec="touches_repo"), project, "spec", "README.md")


class TestTestGates:
    def test_test_stage_may_only_add_files_under_the_agent_tests(self, project):
        assert_stopped(run(project, test="touches_app"), project, "test", "agent_llm.py")

    def test_test_named_by_the_spec_must_exist(self, project):
        assert_stopped(run(project, test="missing_test"), project, "test", "test_offline_env_is_agent_scoped")

    def test_red_gate_stops_a_test_that_already_passes(self, project):
        assert_stopped(run(project, test="passes_already"), project, "red-gate", "passed before implementation")
        assert states(project) == ["spec", "scaffold", "test"]


class TestImplementGates:
    def test_editing_the_tests_stops(self, project):
        assert_stopped(run(project, implement="touches_tests"), project, "implement", "tests/test_agent_contract.py")

    def test_editing_files_outside_the_agent_stops(self, project):
        assert_stopped(run(project, implement="touches_other"), project, "implement", "README.md")

    def test_failing_suite_stops_at_green_gate(self, project):
        assert_stopped(run(project, implement="broken"), project, "green-gate", "suite fails")

    @pytest.mark.parametrize("behaviour,reason", [
        ("leftover_names", "example_agent"),
        ("parent_env", "agent_env.py"),
        ("wide_bind", "0.0.0.0"),
        ("thin_readme", "retention"),
    ])
    def test_hygiene_gate(self, project, behaviour, reason):
        assert_stopped(run(project, implement=behaviour), project, "hygiene-gate", reason)

    def test_readme_may_link_to_the_reference_it_was_built_from(self, project):
        proc = run(project, implement="readme_provenance")
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_reference_path_name_in_code_is_still_a_leftover(self, project):
        assert_stopped(run(project, implement="code_hyphen_name"), project, "hygiene-gate", "example-agent")

    def test_set_aside_patch_is_kept(self, project):
        run(project, implement="broken")
        assert (run_dir(project) / "rejected-implement.patch").stat().st_size > 0


class TestReviewGates:
    def test_review_asking_for_changes_stops(self, project):
        assert_stopped(run(project, review="changes"), project, "verdict-gate", "The README omits setup.")

    def test_non_json_review_stops(self, project):
        assert_stopped(run(project, review="garbage"), project, "review", "no valid verdict")


class TestBudgetAndSafety:
    def test_over_budget_stops_next_stage(self, project):
        proc = run(project, FACTORY_FAKE_EXPENSIVE="spec", FACTORY_MAX_COST_USD="5")
        assert_stopped(proc, project, "test", "budget")

    def test_users_own_untracked_files_survive_a_stop(self, project):
        mine = project / "scratch-notes.txt"
        mine.write_text("mine")
        proc = run(project, implement="broken")
        assert_stopped(proc, project, "green-gate", "suite fails")
        assert mine.read_text() == "mine"


class TestRateLimits:
    def test_a_rate_limited_stage_is_retried_after_discarding_partial_work(self, project):
        proc = run(project, implement="rate_limit_once", FACTORY_RETRY_WAIT="0")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert calls(project) == ["spec", "test", "implement", "implement", "review"]
        assert "rate limited" in (run_dir(project) / "log").read_text()
        git(project, "switch", "-q", "factory/" + RUN_ID)
        assert not (project / "agents" / "demo-scout" / "half-done.txt").exists()

    def test_persistent_rate_limit_stops_with_a_clear_reason(self, project):
        proc = run(project, implement="rate_limit_always", FACTORY_RETRY_WAIT="0", FACTORY_RETRIES="2")
        assert_stopped(proc, project, "implement", "rate limit")
        assert calls(project).count("implement") == 3   # first try + 2 retries


class TestImplementPasses:
    def test_a_pass_that_changes_nothing_is_followed_by_another_with_feedback(self, project):
        proc = run(project, implement="lazy_once", FACTORY_IMPLEMENT_PASSES="3")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert calls(project) == ["spec", "test", "implement", "implement", "review"]
        assert "implement pass 1/3 left the suite failing" in (run_dir(project) / "log").read_text()

    def test_the_failing_output_is_given_to_the_next_pass(self, project):
        run(project, implement="lazy_once", FACTORY_IMPLEMENT_PASSES="3")
        prompts = (run_dir(project) / "fake-prompts").read_text()
        assert prompts.count("Pass 2 of 3") == 1 and "test_offline_env_is_agent_scoped" in prompts

    def test_passes_are_bounded_and_the_final_stop_names_the_problem(self, project):
        proc = run(project, implement="lazy_always", FACTORY_IMPLEMENT_PASSES="2")
        assert_stopped(proc, project, "implement", "changed nothing")
        assert calls(project).count("implement") == 2


class TestMechanicalScaffold:
    """Renames are the script's job: the model never has to read the reference to do them."""

    def scaffold_file(self, project, path: str) -> str:
        run(project, test="passes_already")   # stops at the RED gate; scaffold is committed by then
        sha = [l.split()[1] for l in states_lines(project) if l.startswith("scaffold ")][0]
        return git(project, "show", f"{sha}:agents/demo-scout/{path}")

    def test_modules_settings_and_names_are_renamed_by_the_script(self, project):
        assert 'OFFLINE_ENV = "DEMO_SCOUT_OFFLINE"' in self.scaffold_file(project, "agent_llm.py")
        assert "demo_scout_core" in self.scaffold_file(project, "demo_scout_service.py")
        assert "example" not in self.scaffold_file(project, "demo_scout_service.py").lower().replace("for example", "")

    def test_entry_point_and_title_match_the_text_that_refers_to_them(self, project):
        assert self.scaffold_file(project, "demo_scout.py")   # git show fails if the entry point is misnamed
        sha = [l.split()[1] for l in states_lines(project) if l.startswith("scaffold ")][0]
        assert subprocess.run(["git", "grep", "-iq", "example agent", sha, "--", "agents/demo-scout"],
                              cwd=project).returncode == 1
        assert "Demo Scout" in git(project, "grep", "-h", "Demo Scout", sha, "--", "agents/demo-scout/agent_cli.py", "agents/demo-scout/demo_scout.py")

    def test_env_loading_is_confined_to_the_agent_folder(self, project):
        env = self.scaffold_file(project, "agent_env.py")
        assert "parents" not in env and "[AGENT_DIR]" in env
        assert "parent directory" not in env and "repo root" not in env   # the docstring must not say the opposite


def states_lines(project):
    return (run_dir(project) / "state").read_text().splitlines()


class TestPassFocus:
    def test_the_next_pass_is_pointed_at_the_first_failing_test_file(self, project):
        run(project, implement="lazy_once", FACTORY_IMPLEMENT_PASSES="3")
        second = (run_dir(project) / "fake-prompts").read_text().split("=====")[3]
        assert "Focus this pass on: agents/demo-scout/tests/test_agent_contract.py" in second


class TestReviewRounds:
    def test_findings_are_fixed_and_the_change_is_reviewed_again(self, project):
        proc = run(project, review="changes_once", FACTORY_REVIEW_ROUNDS="2")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert calls(project) == ["spec", "test", "implement", "review", "test", "implement", "review"]
        prompts = (run_dir(project) / "fake-prompts").read_text().split("=====")
        fix_prompt = [p for p in prompts if "You are the implement stage" in p][1]
        assert "Review round 1 of 2" in fix_prompt and "Negative limit drops items." in fix_prompt
        log = git(project, "log", "--format=%s", "factory/" + RUN_ID)
        assert "address review round 1" in log and "tests for review round 1" in log
        test_prompt = [p for p in prompts if "You are the test stage" in p][1]
        assert "Negative limit drops items." in test_prompt
        git(project, "switch", "-q", "factory/" + RUN_ID)
        assert (project / "agents" / "demo-scout" / "tests" / "test_review_round_1.py").exists()
        assert "review round" in (run_dir(project) / "log").read_text()

    def test_persistent_findings_stop_after_the_last_round(self, project):
        proc = run(project, review="changes", FACTORY_REVIEW_ROUNDS="1")
        assert_stopped(proc, project, "verdict-gate", "The README omits setup.")
        assert calls(project).count("review") == 2 and calls(project).count("implement") == 2 and calls(project).count("test") == 2

    def test_a_fix_that_breaks_the_suite_still_stops_at_the_green_gate(self, project):
        proc = run(project, review="changes_once", implement="broken_on_fix", FACTORY_REVIEW_ROUNDS="2")
        assert_stopped(proc, project, "green-gate", "suite fails")

    def test_a_review_round_may_add_tests_but_never_edit_existing_ones(self, project):
        proc = run(project, review="changes_once", test="edits_existing_on_review", FACTORY_REVIEW_ROUNDS="2")
        assert_stopped(proc, project, "test", "existing test lines")
