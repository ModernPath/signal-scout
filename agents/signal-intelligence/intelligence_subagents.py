"""Bounded JSON process contract for the agent's three delegated jobs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
ALLOWED = {"topic_analyst", "evidence_researcher", "draft_writer"}


class SubagentError(RuntimeError):
    """Safe failure from a delegated job."""


class SubagentRunner:
    def __init__(self, *, directory: Path | None = None, timeout: int = 90, database_url: str | None = None):
        self.directory = Path(directory) if directory else AGENT_DIR / "subagents"
        self.timeout = timeout
        self.database_url = database_url

    def run(self, name: str, payload: dict) -> dict:
        if name not in ALLOWED or not (self.directory / f"{name}.py").is_file():
            raise SubagentError(f"Unknown subagent: {name}")
        if len(json.dumps(payload)) > 4096:
            raise SubagentError("Subagent request is too large")
        env = {key: value for key, value in os.environ.items() if key in
               {"PATH", "DATABASE_URL", "GEMINI_API_KEY", "SIGNAL_INTELLIGENCE_MODEL",
                "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"}}
        if self.database_url is not None:
            env['DATABASE_URL']=self.database_url
        try:
            result = subprocess.run([sys.executable, str(self.directory / f"{name}.py")],
                                    input=json.dumps(payload), capture_output=True,
                                    text=True, timeout=self.timeout, cwd=AGENT_DIR, env=env)
        except subprocess.TimeoutExpired:
            raise SubagentError(f"{name} timed out") from None
        if len(result.stdout) > 100_000:
            raise SubagentError(f"{name} output is too large")
        try:
            message = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            raise SubagentError(f"{name} returned invalid JSON") from None
        if result.returncode != 0 or not isinstance(message, dict) or message.get("status") != "success":
            raise SubagentError(f"{name} failed")
        data = message.get("data")
        if not isinstance(data, dict):
            raise SubagentError(f"{name} returned invalid data")
        return data
