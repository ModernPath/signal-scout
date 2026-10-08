"""Shared fixtures. Every test runs offline against a throwaway data dir."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

OFFLINE_ENV = "READING_LIST_OFFLINE"
DATA_DIR_ENV = "READING_LIST_DATA_DIR"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Force offline mode and a temp data dir; also inherited by subprocesses."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv(OFFLINE_ENV, "1")
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    for key in ("GEMINI_API_KEY", "GOOGLE_AI_STUDIO_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    return data_dir


@pytest.fixture
def store(isolated_env: Path):
    from memory.memory import ReadingListStore

    return ReadingListStore(isolated_env)


@pytest.fixture
def seed(isolated_env: Path):
    """Write item records straight to items.json (to control added_at / read_at)."""

    def write(*rows: dict) -> Path:
        isolated_env.mkdir(parents=True, exist_ok=True)
        path = isolated_env / "items.json"
        full = [{"note": "", "tags": [], "read_at": None, **row} for row in rows]
        path.write_text(json.dumps(full), encoding="utf-8")
        return path

    return write


@pytest.fixture
def run_script() -> Callable[..., subprocess.CompletedProcess]:
    """Run an agent script (path relative to the agent folder) with the test env."""

    def run(script: str, *args: str, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(AGENT_DIR / script), *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=str(AGENT_DIR),
            timeout=60,
        )

    return run
