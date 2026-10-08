#!/usr/bin/env python3
"""Prove each security check is load-bearing: remove it, run the tests, put it back.

A refusing test that still passes with the check removed proves nothing. This
script removes one check at a time, runs the suite, prints which tests went
red, and restores the file. Run from secure-agent/:

  python scripts/prove_guards.py

Every line must say RED. "STILL GREEN" names a check no test protects.
Do not edit files while it runs: it rewrites them and restores them.
"""

import pathlib
import subprocess
import sys

PY = sys.executable
M = [
 ("ownership filter in NoteStore.all", "memory/memory.py", 'if row.get("owner") == owner]', 'if True]'),
 ("owner check in ActionStore.decide", "memory/memory.py", 'if row["id"] == action_id and row["owner"] == owner:\n                    new_status', 'if row["id"] == action_id:\n                    new_status'),
 ("file lock around read-modify-write", "memory/memory.py", "fcntl.flock(handle, fcntl.LOCK_EX)", "pass"),
 ("token check in current_user", "api/main.py", "    if not user:\n        raise HTTPException(", "    user = user or 'alice'\n    if not user:\n        raise HTTPException("),
 ("digest check in check_approvable", "example_core.py", "        if digest != self.digest:", "        if False:"),
 ("expiry check in check_approvable", "example_core.py", "        if self.is_expired(now):", "        if False:"),
 ("per-turn tool budget", "example_chat.py", "        if self.calls_left <= 0:", "        if False:"),
 ("model gets a direct delete tool", "example_chat.py", "    return [add_note, search_notes, request_delete, summarize_notes]",
  "    @tool\n    def delete_note(note_ids: str) -> Dict[str, Any]:\n        \"\"\"Delete notes.\"\"\"\n        return {\"deleted\": [service.delete_note(store, user, i.strip())['id'] for i in note_ids.split(',')]}\n\n    return [add_note, search_notes, request_delete, summarize_notes, delete_note]"),
 ("daily model-turn cap", "memory/memory.py", "            if today.get(owner, 0) >= limit:", "            if False:"),
 ("env files read from parent folders", "agent_env.py", "    for name in ENV_FILES:\n        path = AGENT_DIR / name\n        if path.is_file():\n            load_dotenv(path, override=True)",
  "    for directory in reversed([AGENT_DIR, *AGENT_DIR.parents]):\n        for name in ENV_FILES:\n            path = directory / name\n            if path.is_file():\n                load_dotenv(path, override=True)"),
]
hollow = 0
for name, f, old, new in M:
    p = pathlib.Path(f); src = p.read_text()
    assert src.count(old) == 1, (name, src.count(old))
    p.write_text(src.replace(old, new))
    try:
        r2 = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:warnings", "--no-header", "-rf"], capture_output=True, text=True)
        fails = [l.split(" - ")[0].replace("FAILED ","") for l in r2.stdout.splitlines() if l.startswith("FAILED")]
        hollow += not fails
        print(f"## {name}: {'RED' if fails else 'STILL GREEN (hollow!)'} — {len(fails)} failing")
        for x in fails: print("   ", x)
    finally:
        p.write_text(src)
r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:warnings"], capture_output=True, text=True)
print("restored:", r.stdout.strip().splitlines()[-1])
sys.exit(1 if hollow or r.returncode else 0)
