#!/usr/bin/env python3
"""
Create API users for Secure Agent. The token is printed once; only its hash is stored.

Usage:
  python manage_users.py add alice
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_env import load_agent_environment  # noqa: E402
from memory.memory import NoteStore, UserStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("add", help="Create a user and print its token once").add_argument("user")
    args = parser.parse_args()

    load_agent_environment()
    store = NoteStore()
    try:
        token = UserStore(store.data_dir).add(args.user)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Created {args.user}. Token (shown once, store it safely):\n{token}")


if __name__ == "__main__":
    main()
