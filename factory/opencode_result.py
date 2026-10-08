#!/usr/bin/env python3
"""Turn `opencode run --format json` events (stdin) into a `claude -p`-shaped result.

    opencode run ... | python3 factory/opencode_result.py <exit code> <model>

The answer is the text of the last step; turns and cost are summed from
step-finish events. An error event, a non-zero exit, or a stream that never
finishes a step counts as an error, because opencode exits 0 after some failures.
"""

import json
import sys


def convert(lines, returncode: int, model: str) -> dict:
    turns, cost, texts, errors, finished = 0, 0.0, [], [], False
    tokens, peak = 0, 0
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind, part = event.get("type"), event.get("part") or {}
        if kind == "step_start":
            texts = []
        elif kind == "text":
            texts.append(part.get("text", ""))
        elif kind == "step_finish":
            turns, finished = turns + 1, True
            cost += float(part.get("cost") or 0)
            used = int((part.get("tokens") or {}).get("total") or 0)
            tokens, peak = tokens + used, max(peak, used)
        elif kind == "error":
            data = (event.get("error") or {}).get("data") or {}
            errors.append(data.get("message") or json.dumps(event.get("error")))
    failed = bool(errors) or returncode != 0 or not finished
    return {
        "subtype": "error" if failed else "success",
        "is_error": failed,
        "result": "\n".join(errors) if errors else "".join(texts),
        "num_turns": turns,
        "total_cost_usd": cost,
        "total_tokens": tokens,
        "peak_request_tokens": peak,
        "modelUsage": {model: {}},
    }


if __name__ == "__main__":
    print(json.dumps(convert(sys.stdin, int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "default")))
