"""Load .env / .env.local from the agent folder only.

example-agent also reads every parent folder, so inside another project's
checkout it picks up that project's API keys. This agent's secrets live next to
it, in an ignored .env.local, and nowhere else is read.
"""

from __future__ import annotations

from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
ENV_FILES = (".env", ".env.local")


def load_agent_environment() -> None:
    from dotenv import load_dotenv

    for name in ENV_FILES:
        path = AGENT_DIR / name
        if path.is_file():
            load_dotenv(path, override=True)
