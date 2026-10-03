"""Shared setup for standalone tool scripts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import print_result  # noqa: E402
from agent_env import make_service  # noqa: E402


def read_json(path: str) -> dict:
    import json

    file = Path(path)
    if file.stat().st_size > 100_000:
        raise ValueError("Input JSON file is too large")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input file must contain a JSON object")
    return data
