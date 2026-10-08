"""Load .env / .env.local from the agent folder only.

Parent directories are never read, so unrelated project credentials cannot leak in.
Variables already set in the process win; .env.local wins over .env.
"""

from __future__ import annotations

from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent


def load_agent_environment() -> None:
    from dotenv import load_dotenv

    for directory in [AGENT_DIR]:
        for name in (".env.local", ".env"):
            path = directory / name
            if path.is_file():
                load_dotenv(path, override=False)
