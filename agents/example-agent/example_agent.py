#!/usr/bin/env python3
"""
Example Agent CLI — a minimal, clean template for building agents in this folder.

Usage:
  python example_agent.py --chat                      # Interactive mode
  python example_agent.py "what notes do I have?"     # Single query
  python example_agent.py --offline "add Call Bob #work"
  python example_agent.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_llm  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_chat import chat_reply  # noqa: E402
from memory.memory import NoteStore  # noqa: E402

EXIT_COMMANDS = {"exit", "quit", ":q"}


def chat_loop(store: NoteStore, *, offline: bool) -> None:
    mode = "offline" if offline or not agent_llm.llm_available() else agent_llm.model_name()
    print(f"Example Agent ({mode}). Type 'exit' to quit.\n")

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
    parser = argparse.ArgumentParser(description="Example Agent — manage notes with an AI agent")
    parser.add_argument("query", nargs="?", help="Single question or command")
    parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    parser.add_argument("--offline", action="store_true", help="Skip the LLM; use the rule-based router")
    args = parser.parse_args()

    load_agent_environment()
    store = NoteStore()

    if args.chat:
        chat_loop(store, offline=args.offline)
    elif args.query:
        print(chat_reply(store, args.query, offline=args.offline).reply)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
