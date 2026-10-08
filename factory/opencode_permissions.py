#!/usr/bin/env python3
"""Turn a Claude-style tool list into opencode's deny-by-default permission config.

    python3 factory/opencode_permissions.py "Read,Grep,Bash(git mv:*)"

opencode has no --allowedTools; its permission boundary is the `permission`
config. Everything is denied unless the stage lists it, and web access and
paths outside the repository stay denied.
"""

import json
import re
import sys

SIMPLE = {"Read": "read", "Grep": "grep", "Glob": "glob", "Edit": "edit", "Write": "edit"}


def split_tools(tools: str) -> list:
    return re.findall(r"[A-Za-z]+(?:\([^)]*\))?", tools)


def build(tools: str) -> dict:
    permission = {"*": "deny", "bash": {"*": "deny"}, "webfetch": "deny", "external_directory": "deny"}
    for tool in split_tools(tools):
        name, _, arg = tool.partition("(")
        if name in SIMPLE:
            permission[SIMPLE[name]] = "allow"
        elif name == "Bash" and arg:
            command = arg.rstrip(")")
            command = command[:-2] + " *" if command.endswith(":*") else command
            permission["bash"][command] = "allow"
    return {"permission": permission}


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1])))
