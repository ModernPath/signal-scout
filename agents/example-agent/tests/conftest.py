"""Shared fixtures. Every test runs offline against a throwaway data dir."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from agent_llm import OFFLINE_ENV  # noqa: E402
from memory.memory import DATA_DIR_ENV, NoteStore  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Force offline mode and a temp data dir — also inherited by subprocesses."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv(OFFLINE_ENV, "1")
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    return data_dir


@pytest.fixture
def store(isolated_env: Path) -> NoteStore:
    return NoteStore(isolated_env)


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
