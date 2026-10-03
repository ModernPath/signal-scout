"""End-to-end checks of every CLI entry point, run as real subprocesses."""

from __future__ import annotations

import json


def _ok(proc) -> dict:
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    return payload


def test_tools_round_trip(run_script):
    note = _ok(run_script("tools/add_note.py", "--title", "Call Bob", "--tags", "work"))["data"]
    assert note["tags"] == ["work"]

    found = _ok(run_script("tools/search_notes.py", "--query", "bob"))["data"]
    assert [n["id"] for n in found] == [note["id"]]

    _ok(run_script("tools/delete_note.py", "--id", note["id"]))
    assert _ok(run_script("tools/search_notes.py"))["data"] == []


def test_tool_error_envelope(run_script):
    proc = run_script("tools/delete_note.py", "--id", "note_missing")
    assert proc.returncode == 1
    assert json.loads(proc.stdout) == {"status": "error", "error": "Note not found: note_missing"}


def test_memory_cli(run_script):
    run_script("tools/add_note.py", "--title", "A", "--tags", "x")
    notes = _ok(run_script("memory/memory.py", "list"))["data"]
    assert _ok(run_script("memory/memory.py", "get", "--id", notes[0]["id"]))["data"]["title"] == "A"
    assert _ok(run_script("memory/memory.py", "stats"))["data"] == {"total": 1, "tags": {"x": 1}}


def test_subagent(run_script):
    run_script("tools/add_note.py", "--title", "Call Bob", "--tags", "work")
    payload = _ok(run_script("subagents/note_summarizer.py", "--tag", "work"))
    assert payload["subagent"] == "note_summarizer"
    assert payload["data"]["note_count"] == 1


def test_main_cli(run_script):
    assert "Example Agent" in run_script("example_agent.py", "--help").stdout

    added = run_script("example_agent.py", "add Buy milk #home")
    assert added.returncode == 0 and "Saved" in added.stdout
    assert "Buy milk" in run_script("example_agent.py", "list notes").stdout


def test_main_cli_chat_mode(run_script):
    proc = run_script("example_agent.py", "--chat", stdin="add Buy milk\nlist notes\nexit\n")
    assert proc.returncode == 0
    assert "[tools: add_note]" in proc.stdout
    assert "Agent: Your notes:" in proc.stdout
