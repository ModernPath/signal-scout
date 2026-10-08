"""Shared JSON output contract for tool and memory CLIs.

Every CLI prints exactly one JSON object and exits 0 on success, 1 on error:
  {"status": "success", "data": ...}
  {"status": "error", "error": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, NoReturn

from agent_env import load_agent_environment

EXPECTED_ERRORS = (ValueError, LookupError, RuntimeError)


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument errors become the JSON error envelope (exit 1), not usage on stderr."""

    def error(self, message: str) -> NoReturn:
        print(json.dumps({"status": "error", "error": message}))
        sys.exit(1)


def make_parser(description: str) -> JsonArgumentParser:
    """Parser for a CLI entry point; also loads the agent folder's .env files so
    tools, memory CLI and API resolve the same data directory."""
    load_agent_environment()
    return JsonArgumentParser(description=description)


def run_and_print(action: Callable[[], Any], **extra: Any) -> NoReturn:
    """Run `action`, print the JSON envelope, and exit with the matching code."""
    try:
        data = action()
    except EXPECTED_ERRORS as exc:
        print(json.dumps({**extra, "status": "error", "error": str(exc)}))
        sys.exit(1)
    print(json.dumps({**extra, "status": "success", "data": data}, ensure_ascii=False))
    sys.exit(0)
