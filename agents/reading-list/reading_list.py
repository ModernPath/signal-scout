#!/usr/bin/env python3
"""
Reading List CLI — save links, tag them, and get a deterministic read-next ranking.

Usage:
  python reading_list.py --chat                      # Interactive mode
  python reading_list.py "what should I read next?"  # Single query
  python reading_list.py --offline "add Title https://example.com #work"
  python reading_list.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_llm  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from reading_list_chat import chat_reply  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402

EXIT_COMMANDS = {"exit", "quit", ":q"}


def chat_loop(store: ReadingListStore, *, offline: bool) -> None:
    mode = "offline" if offline or not agent_llm.llm_available() else agent_llm.model_name()
    print(f"Reading List ({mode}). Type 'exit' to quit.\n")

    history: list[dict[str, str]] = []
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if message.lower() in EXIT_COMMANDS:
            return
        if not message:
            continue

        result = chat_reply(store, message, history=history, offline=offline)
        history = result.history
        if result.tools_used:
            print(f"  [tools: {', '.join(result.tools_used)}]")
        print(f"Agent: {result.reply}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reading List — manage a reading list")
    parser.add_argument("query", nargs="?", help="Single question or command")
    parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    parser.add_argument("--offline", action="store_true", help="Skip the LLM; use the rule-based router")
    args = parser.parse_args()

    load_agent_environment()
    store = ReadingListStore()

    if args.chat:
        chat_loop(store, offline=args.offline)
    elif args.query:
        print(chat_reply(store, args.query, offline=args.offline).reply)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
