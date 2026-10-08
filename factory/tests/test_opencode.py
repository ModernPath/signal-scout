"""The opencode backend's two adapters, tested without opencode itself.

opencode_permissions.py turns a stage's Claude-style tool list into opencode's
deny-by-default permission config; opencode_result.py turns opencode's JSON
event stream into the result object run.sh expects from `claude -p`.
"""

from __future__ import annotations

import pytest  # noqa: F401  (fixtures come from test_factory)

import json
import os
import subprocess
import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]


def permissions(tools: str) -> dict:
    out = subprocess.run([sys.executable, str(FACTORY / "opencode_permissions.py"), tools],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["permission"]


def result(events: list, returncode: int = 0, model: str = "p/m") -> dict:
    stream = "\n".join(e if isinstance(e, str) else json.dumps(e) for e in events)
    out = subprocess.run([sys.executable, str(FACTORY / "opencode_result.py"), str(returncode), model],
                         input=stream, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def finish(cost: float, reason: str, tokens: int = 0) -> dict:
    return {"type": "step_finish", "part": {"type": "step-finish", "cost": cost, "reason": reason,
                                            "tokens": {"total": tokens}}}


def text(value: str) -> dict:
    return {"type": "text", "part": {"type": "text", "text": value}}


class TestPermissions:
    def test_everything_is_denied_unless_the_stage_lists_it(self):
        p = permissions("Read,Grep,Glob")
        assert p["*"] == "deny"
        assert (p["read"], p["grep"], p["glob"]) == ("allow", "allow", "allow")
        assert p.get("edit", "deny") == "deny" and p["bash"] == {"*": "deny"}
        assert p["webfetch"] == "deny" and p["external_directory"] == "deny"

    def test_write_and_edit_map_to_edit(self):
        assert permissions("Read,Write")["edit"] == "allow"
        assert permissions("Edit")["edit"] == "allow"

    def test_bash_patterns_become_command_globs(self):
        p = permissions("Read,Bash(bash factory/check.sh:*),Bash(git mv:*)")
        assert p["bash"] == {"*": "deny", "bash factory/check.sh *": "allow", "git mv *": "allow"}


class TestResult:
    def test_final_text_turns_and_cost(self):
        r = result([{"type": "step_start"}, finish(0.25, "tool-calls"), {"type": "step_start"},
                    text("done"), finish(0.5, "stop")])
        assert r["subtype"] == "success" and r["is_error"] is False
        assert r["result"] == "done" and r["num_turns"] == 2 and r["total_cost_usd"] == 0.75
        assert r["modelUsage"] == {"p/m": {}}

    def test_total_and_peak_tokens_are_reported(self):
        r = result([finish(0, "tool-calls", 1000), finish(0, "tool-calls", 5000), text("x"), finish(0, "stop", 3000)])
        assert r["total_tokens"] == 9000 and r["peak_request_tokens"] == 5000

    def test_only_the_last_step_text_is_the_answer(self):
        r = result([text("thinking aloud"), finish(0, "tool-calls"), {"type": "step_start"}, text('{"verdict": "approve"}'), finish(0, "stop")])
        assert r["result"] == '{"verdict": "approve"}'

    def test_error_event_is_an_error_even_with_exit_zero(self):
        r = result([{"type": "error", "error": {"name": "UnknownError", "data": {"message": "boom"}}}])
        assert r["is_error"] is True and r["subtype"] == "error" and "boom" in r["result"]

    def test_nonzero_exit_is_an_error(self):
        assert result([text("partial"), finish(0, "stop")], returncode=1)["is_error"] is True

    def test_garbage_lines_are_ignored(self):
        assert result(["not json", text("ok"), finish(0, "stop")])["result"] == "ok"

    def test_a_stream_that_never_finishes_is_an_error(self):
        assert result([text("cut off")])["is_error"] is True


class TestBackendWiring:
    """run.sh with a stub `opencode` on PATH: checks the command line, config and stop on error."""

    def stub(self, tmp_path: Path, body: str) -> dict:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        script = bin_dir / "opencode"
        script.write_text("#!/usr/bin/env bash\n" + body)
        script.chmod(0o755)
        return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FACTORY_BACKEND": "opencode",
                "FACTORY_MODEL": "stub/model"}

    def start(self, project, env):
        return subprocess.run(["bash", "factory/run.sh", "factory/briefs/001-demo-scout.md"], cwd=project,
                              env=env, capture_output=True, text=True, timeout=120)

    def test_stage_runs_with_isolated_config_and_spec_permissions(self, project, tmp_path):
        record = tmp_path / "record.txt"
        env = self.stub(tmp_path, f'''{{ echo "$@" | cut -c1-60; echo "XDG=$XDG_CONFIG_HOME"; echo "CFG=$OPENCODE_CONFIG_CONTENT"; }} > {record}
echo '{{"type":"step_finish","part":{{"type":"step-finish","cost":0,"reason":"stop"}}}}'
''')
        proc = self.start(project, env)
        recorded = record.read_text()
        assert "run --pure --format json -m stub/model" in recorded
        assert "factory/runs/001-demo-scout/.opencode-config" in recorded
        cfg = json.loads(recorded.split("CFG=", 1)[1])["permission"]
        assert cfg["edit"] == "allow" and cfg["bash"] == {"*": "deny"}   # spec stage: Write, no Bash
        # The stub wrote no spec.md, so the spec gate (not the backend) stops the run.
        assert proc.returncode == 1 and "spec.md is missing" in (project / "factory/runs/001-demo-scout/stop.md").read_text()
        assert "model=stub/model" in (project / "factory/runs/001-demo-scout/log").read_text()

    def test_error_event_with_exit_zero_stops_the_run(self, project, tmp_path):
        env = self.stub(tmp_path, '''echo '{"type":"error","error":{"name":"UnknownError","data":{"message":"model not found"}}}'\n''')
        proc = self.start(project, env)
        assert proc.returncode == 1
        stop = (project / "factory/runs/001-demo-scout/stop.md").read_text()
        assert "stage=spec" in stop and "agent ended with error" in stop
