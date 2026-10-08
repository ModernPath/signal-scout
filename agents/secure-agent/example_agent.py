#!/usr/bin/env python3
"""
Secure Agent CLI.

The CLI runs on your machine as one local user (default "me", or --user).
When the agent asks to delete notes, the CLI shows exactly what would be
deleted and asks you; the model never sees or answers that question.

Usage:
  python example_agent.py --chat
  python example_agent.py "what notes do I have?"
  python example_agent.py --offline "delete note_ab12cd34ef"     # prints the pending action
  python example_agent.py --approve act_0123456789ab --digest <digest>
  python example_agent.py --reject act_0123456789ab
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_llm  # noqa: E402
import example_service as service  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_chat import chat_reply  # noqa: E402
from example_core import ActionStateError, validate_user_id  # noqa: E402
from memory.memory import NoteStore  # noqa: E402

EXIT_COMMANDS = {"exit", "quit", ":q"}
DEFAULT_LOCAL_USER = "me"


def confirm_actions(store: NoteStore, user: str, actions: List[Dict[str, Any]], ask: Callable[[str], str] = input) -> None:
    """Ask the person about each pending action. Anything but 'y' leaves it pending."""
    for action in actions:
        answer = ask(f"  Approve? {action['preview']} [y/N] ").strip().lower()
        if answer == "y":
            done = service.approve_action(store, user, action["id"], action["digest"])
            print(f"  Deleted {len(done['deleted'])} note(s).")
        else:
            print(f"  Not approved. It stays pending until {action['expires_at']} ({action['id']}).")


def chat_loop(store: NoteStore, user: str, *, offline: bool) -> None:
    mode = "offline" if offline or not agent_llm.llm_available() else agent_llm.model_name()
    print(f"Secure Agent ({mode}, user {user}). Type 'exit' to quit.\n")

    history: list = []
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

        result = chat_reply(store, user, message, history=history, offline=offline)
        history = result.history
        if result.tools_used:
            print(f"  [tools: {', '.join(result.tools_used)}]")
        print(f"Agent: {result.reply}\n")
        try:
            confirm_actions(store, user, result.pending_actions)
        except EOFError:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Secure Agent — notes with per-user access and approvals")
    parser.add_argument("query", nargs="?", help="Single question or command")
    parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    parser.add_argument("--offline", action="store_true", help="Skip the LLM; use the rule-based router")
    parser.add_argument("--user", default=DEFAULT_LOCAL_USER, help="Local user whose notes to use")
    parser.add_argument("--approve", metavar="ACTION_ID", help="Approve a pending action")
    parser.add_argument("--digest", help="Digest shown with the action's preview (needed with --approve)")
    parser.add_argument("--reject", metavar="ACTION_ID", help="Reject a pending action")
    args = parser.parse_args()

    load_agent_environment()
    store = NoteStore()
    user = validate_user_id(args.user)

    try:
        if args.approve:
            if not args.digest:
                parser.error("--approve needs --digest from the action's preview")
            print(json.dumps(service.approve_action(store, user, args.approve, args.digest), ensure_ascii=False))
        elif args.reject:
            print(json.dumps(service.reject_action(store, user, args.reject), ensure_ascii=False))
        elif args.chat:
            chat_loop(store, user, offline=args.offline)
        elif args.query:
            result = chat_reply(store, user, args.query, offline=args.offline)
            print(result.reply)
            for action in result.pending_actions:
                print(f"Pending {action['id']} digest {action['digest']}: approve with "
                      f"--approve {action['id']} --digest {action['digest']}")
        else:
            parser.print_help()
    except (ActionStateError, LookupError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
