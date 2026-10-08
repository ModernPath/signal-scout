"""Shared JSON output contract for tool, subagent, and memory CLIs.

Every CLI prints exactly one JSON object and exits 0 on success, 1 on error:
  {"status": "success", "data": ...}
  {"status": "error", "error": "..."}
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, NoReturn

EXPECTED_ERRORS = (ValueError, LookupError, RuntimeError)


def run_and_print(action: Callable[[], Any], **extra: Any) -> NoReturn:
    """Run `action`, print the JSON envelope, and exit with the matching code."""
    try:
        data = action()
    except EXPECTED_ERRORS as exc:
        print(json.dumps({**extra, "status": "error", "error": str(exc)}))
        sys.exit(1)
    print(json.dumps({**extra, "status": "success", "data": data}, ensure_ascii=False))
    sys.exit(0)
