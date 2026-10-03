"""Load .env / .env.local from the agent folder and each parent directory.

Files closer to the agent win, so a session-level .env.local overrides the repo root.
"""

from __future__ import annotations

from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent


def load_agent_environment() -> None:
    from dotenv import load_dotenv

    for directory in reversed([AGENT_DIR, *AGENT_DIR.parents]):
        for name in (".env", ".env.local"):
            path = directory / name
            if path.is_file():
                load_dotenv(path, override=True)
