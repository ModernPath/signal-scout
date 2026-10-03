#!/usr/bin/env python3
"""Local JSON CLI for the standalone SignalScout intelligence agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent_env import make_service as configured_service
from intelligence_chat import chat_reply
from intelligence_service import IntelligenceService

DIRECT_COMMANDS = {"brief", "content", "analyze", "opportunities", "research", "draft"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone SignalScout intelligence agent")
    sub = parser.add_subparsers(dest="command", required=True)
    brief = sub.add_parser("brief")
    brief_sub = brief.add_subparsers(dest="action", required=True)
    brief_sub.add_parser("show")
    brief_sub.add_parser("set").add_argument("file", help="JSON company brief")
    brief_sub.add_parser("delete")
    content = sub.add_parser("content")
    content_sub = content.add_subparsers(dest="action", required=True)
    content_sub.add_parser("list")
    content_sub.add_parser("add").add_argument("file", help="JSON content item")
    replace = content_sub.add_parser("replace")
    replace.add_argument("id", type=int)
    replace.add_argument("file", help="JSON content item")
    content_sub.add_parser("delete").add_argument("id", type=int)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--days", type=int, default=30)
    analyze.add_argument("--limit", type=int, default=500)
    opportunities = sub.add_parser("opportunities")
    opportunities_sub = opportunities.add_subparsers(dest="action", required=True)
    opportunities_sub.add_parser("list")
    opportunities_sub.add_parser("show").add_argument("id", type=int)
    research = sub.add_parser("research")
    research.add_argument("id", type=int)
    draft = sub.add_parser("draft")
    draft.add_argument("id", type=int)
    draft.add_argument("--channel", choices=("linkedin", "x"), required=True)
    draft.add_argument("--format", choices=("post", "reply"), required=True)
    return parser


def make_service() -> IntelligenceService:
    return configured_service()


def read_json(path: str) -> dict:
    file = Path(path)
    if file.stat().st_size > 100_000:
        raise ValueError("Input JSON file is too large")
    value = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Input file must contain a JSON object")
    return value


def main(argv: list[str] | None = None, *, service: IntelligenceService | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--chat" in argv or "--offline" in argv or \
            (argv and argv[0] not in DIRECT_COMMANDS and not argv[0].startswith("-")):
        offline = "--offline" in argv
        interactive = "--chat" in argv
        words = [part for part in argv if part not in ("--offline", "--chat")]
        try:
            agent = service or make_service()
            if interactive:
                session_id = None
                while True:
                    try:
                        message = input("You: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        return 0
                    if message.lower() in ("exit", "quit", ":q"):
                        return 0
                    if not message:
                        continue
                    result = chat_reply(agent, message, session_id=session_id, offline=offline)
                    session_id = result.session_id
                    print(f"Agent: {result.reply}\n")
            else:
                print(chat_reply(agent, " ".join(words), offline=offline).reply)
            return 0
        except (ValueError, LookupError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    args = build_parser().parse_args(argv)
    try:
        if args.command == "analyze" and (not 1 <= args.days <= 90 or not 1 <= args.limit <= 1000):
            raise ValueError("Analysis days and limit are out of range")
        agent = service or make_service()
        if args.command == "brief":
            if args.action == "show":
                data = agent.get_brief()
            elif args.action == "delete":
                data = agent.clear_brief()
            else:
                data = agent.set_brief(read_json(args.file))
        elif args.command == "content":
            if args.action == "list":
                data = agent.list_content()
            elif args.action == "add":
                data = agent.add_content(read_json(args.file))
            elif args.action == "replace":
                data = agent.replace_content(args.id, read_json(args.file))
            else:
                data = agent.delete_content(args.id)
        elif args.command == "analyze":
            data = agent.analyze(days=args.days, limit=args.limit)
        elif args.command == "opportunities":
            data = agent.opportunities() if args.action == "list" else agent.opportunity(args.id)
        elif args.command == "research":
            data = agent.research(args.id)
        else:
            data = agent.draft(args.id, args.channel, args.format)
        print(json.dumps({"status": "success", "data": data}, default=str, ensure_ascii=False))
        return 0
    except (ValueError, LookupError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    except Exception:
        # SQL/provider exceptions can contain credentials or private material.
        print(json.dumps({"status": "error", "error": "Agent operation failed; check local setup and database readiness"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
