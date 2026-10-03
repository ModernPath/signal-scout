"""One safe JSON envelope for tool, memory, and subagent CLIs."""

from __future__ import annotations

import json
import sys


def print_result(action) -> None:
    try:
        data = action()
        print(json.dumps({"status": "success", "data": data}, default=str, ensure_ascii=False))
    except (ValueError, LookupError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        sys.exit(1)
    except Exception:
        print(json.dumps({"status": "error", "error": "Agent operation failed"}))
        sys.exit(1)


def read_request() -> dict:
    raw = sys.stdin.read(4097)
    if len(raw) > 4096:
        raise ValueError("Subagent request is too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Subagent request must be a JSON object")
    return payload
