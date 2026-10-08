"""Shared fixtures. Every test runs offline against a throwaway data dir, with two users."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from agent_llm import OFFLINE_ENV  # noqa: E402
from memory.memory import DATA_DIR_ENV, NoteStore, UserStore  # noqa: E402

ALICE, BOB = "alice", "bob"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Force offline mode and a temp data dir — also inherited by subprocesses."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv(OFFLINE_ENV, "1")
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    # Never read the developer's .env.local in a test.
    monkeypatch.setattr("agent_env.load_agent_environment", lambda: None)
    return data_dir


@pytest.fixture
def store(isolated_env: Path) -> NoteStore:
    return NoteStore(isolated_env)


@pytest.fixture
def tokens(store: NoteStore) -> Dict[str, str]:
    users = UserStore(store.data_dir)
    return {ALICE: users.add(ALICE), BOB: users.add(BOB)}


@pytest.fixture
def client(store: NoteStore):
    from fastapi.testclient import TestClient

    from api.main import app, get_store

    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
