#!/usr/bin/env python3
"""
Generic Gemini CLI template for the agents kit.

Copy this file into an agent folder only when that agent needs Gemini. Agents
can also use a different provider or no model client.

Fill CUSTOM_FUNCTION_DECLARATIONS and execute_custom_function() to expose
local tools. Built-in Gemini tools (search, URL context, code execution)
are optional via --tools.

Usage:
  python gemini_agent.py --chat
  python gemini_agent.py "What time is it in Helsinki?"
  python gemini_agent.py --tools search,url --chat
  python gemini_agent.py --plan "Outline the requested task"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
MAX_TOOL_ROUNDS = 8

# ---------------------------------------------------------------------------
# Extension point: add your agent's CLI tools here (empty = Gemini tools only)
# ---------------------------------------------------------------------------

CUSTOM_FUNCTION_DECLARATIONS: List[Dict[str, Any]] = []


def execute_custom_function(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a custom function declared in CUSTOM_FUNCTION_DECLARATIONS."""
    return {"ok": False, "error": f"No handler for function: {name}", "args": args}


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_env_files() -> None:
    """Load KEY=VALUE from .env then .env.local, walking up from cwd and this file.

    Existing process env wins. .env.local overrides .env in the same directory.
    """
    roots: List[Path] = []
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        directory = start
        while True:
            if directory not in roots:
                roots.append(directory)
            if directory.parent == directory:
                break
            directory = directory.parent

    for directory in reversed(roots):
        for name in (".env", ".env.local"):
            path = directory / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                if name == ".env.local" or key not in os.environ:
                    os.environ[key] = value


def load_api_key() -> str:
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_AI_STUDIO_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not api_key:
        print(
            "Error: set GEMINI_API_KEY, GOOGLE_AI_STUDIO_KEY, or GOOGLE_API_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


# ---------------------------------------------------------------------------
# Gemini tools
# ---------------------------------------------------------------------------

def parse_tool_names(spec: str) -> List[str]:
    names = [part.strip().lower() for part in (spec or "").split(",") if part.strip()]
    if not names or "none" in names:
        return []
    if "all" in names:
        return ["search", "url", "code"]
    allowed = {"search", "url", "code"}
    unknown = [name for name in names if name not in allowed]
    if unknown:
        print(f"Unknown --tools value(s): {', '.join(unknown)} (use search,url,code,all,none)")
        sys.exit(2)
    return names


def build_builtin_tools(names: List[str]) -> List[types.Tool]:
    tools: List[types.Tool] = []
    if "search" in names:
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    if "url" in names:
        tools.append(types.Tool(url_context=types.UrlContext()))
    if "code" in names:
        tools.append(types.Tool(code_execution=types.ToolCodeExecution()))
    return tools


def build_tools(builtin_names: List[str]) -> List[types.Tool]:
    tools = build_builtin_tools(builtin_names)
    if CUSTOM_FUNCTION_DECLARATIONS:
        tools.append(types.Tool(function_declarations=CUSTOM_FUNCTION_DECLARATIONS))
    return tools


def build_system_prompt(builtin_names: List[str]) -> str:
    now = datetime.now()
    custom = "\n".join(
        f"- {item['name']}: {item.get('description', '')}"
        for item in CUSTOM_FUNCTION_DECLARATIONS
    ) or "- (none — add CUSTOM_FUNCTION_DECLARATIONS in gemini_agent.py)"
    builtins = ", ".join(builtin_names) if builtin_names else "none"
    return f"""You are a helpful CLI agent. Prefer tools when they improve factual answers.

Today is {now.strftime("%A, %B %d, %Y")} at {now.strftime("%H:%M")} local time.

Built-in Gemini tools enabled: {builtins}
Custom functions:
{custom}

Call tools when needed, then answer clearly. Do not invent numbers that a custom function should compute.
"""


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def find_function_call_parts(response: Any) -> List[Tuple[str, Dict[str, Any]]]:
    calls: List[Tuple[str, Dict[str, Any]]] = []
    try:
        parts = response.candidates[0].content.parts if response.candidates else []
    except Exception:
        return calls
    for part in parts or []:
        fc = getattr(part, "function_call", None)
        if not fc:
            continue
        name = getattr(fc, "name", "") or ""
        raw_args = getattr(fc, "args", None) or {}
        args = dict(raw_args) if hasattr(raw_args, "items") else {}
        if name:
            calls.append((name, args))
    return calls


def make_function_response_part(name: str, result: Dict[str, Any]) -> types.Part:
    return types.Part(function_response=types.FunctionResponse(name=name, response=result))


def print_response(response: Any) -> None:
    try:
        parts = response.candidates[0].content.parts if response.candidates else []
    except Exception:
        parts = []
    parts = parts or []

    texts = [part.text for part in parts if getattr(part, "text", None)]
    if texts:
        print("\n".join(texts))

    for part in parts:
        code = getattr(getattr(part, "executable_code", None), "code", None)
        if code:
            print("\n# Generated code:\n" + code)
        output = getattr(getattr(part, "code_execution_result", None), "output", None)
        if output:
            print("\n# Execution output:\n" + output)

    try:
        meta = response.candidates[0].grounding_metadata
    except Exception:
        meta = None
    chunks = getattr(meta, "grounding_chunks", None) if meta else None
    if not chunks:
        return
    print("\nSources:")
    for idx, chunk in enumerate(chunks):
        web = getattr(chunk, "web", None)
        uri = getattr(web, "uri", None)
        title = getattr(web, "title", None)
        if uri:
            print(f"[{idx + 1}] {title}: {uri}" if title else f"[{idx + 1}] {uri}")


async def generate_with_tools(
    client: genai.Client,
    model: str,
    contents: List[types.Content],
    tools: List[types.Tool],
) -> Any:
    config = types.GenerateContentConfig(tools=tools) if tools else types.GenerateContentConfig()
    response = await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    for _ in range(MAX_TOOL_ROUNDS):
        calls = find_function_call_parts(response)
        if not calls:
            break
        if response.candidates and response.candidates[0].content:
            contents.append(response.candidates[0].content)
        for name, fargs in calls:
            result = execute_custom_function(name, fargs)
            contents.append(
                types.Content(role="user", parts=[make_function_response_part(name, result)])
            )
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
    return response


def starter_contents(system_prompt: str, user_prompt: Optional[str] = None) -> List[types.Content]:
    contents = [
        types.Content(role="user", parts=[types.Part(text=system_prompt)]),
        types.Content(
            role="model",
            parts=[types.Part(text="Ready. Ask a question or give a task.")],
        ),
    ]
    if user_prompt:
        contents.append(types.Content(role="user", parts=[types.Part(text=user_prompt)]))
    return contents


async def run_single_turn_async(
    client: genai.Client,
    model: str,
    user_prompt: str,
    builtin_names: List[str],
) -> None:
    tools = build_tools(builtin_names)
    contents = starter_contents(build_system_prompt(builtin_names), user_prompt)
    response = await generate_with_tools(client, model, contents, tools)
    print_response(response)


async def run_chat_loop_async(
    client: genai.Client,
    model: str,
    builtin_names: List[str],
) -> None:
    print("Interactive chat. Type 'exit' or Ctrl-D to quit.\n")
    print(f"Built-in tools: {', '.join(builtin_names) or 'none'}; custom functions: {len(CUSTOM_FUNCTION_DECLARATIONS)}")
    system_prompt = build_system_prompt(builtin_names)
    history = starter_contents(system_prompt)
    tools = build_tools(builtin_names)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", ":q", "/exit"}:
            break

        contents = list(history)
        contents.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
        response = await generate_with_tools(client, model, contents, tools)
        print_response(response)
        if response.candidates and response.candidates[0].content:
            history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
            history.append(response.candidates[0].content)


# ---------------------------------------------------------------------------
# Plan mode
# ---------------------------------------------------------------------------

def slugify_filename(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "plan"
    return f"{slug[:80].rstrip('-')}.json"


def extract_json_text(full_text: str) -> str:
    try:
        return json.dumps(json.loads(full_text), separators=(",", ":"))
    except Exception:
        pass
    start, end = full_text.find("{"), full_text.rfind("}")
    if start != -1 and end > start:
        candidate = full_text[start : end + 1]
        try:
            return json.dumps(json.loads(candidate), separators=(",", ":"))
        except Exception:
            return candidate
    return full_text


def run_plan_mode(client: genai.Client, model: str, task: str) -> int:
    prompt = (
        "You are an expert planner. Output JSON only (no markdown) for this schema:\n"
        '{"name": string, "description": string, "start": string, "steps": ['
        '{"id": string, "title": string, "type": "ask_user"|"call_tool"|"decide"|"action"|"compute",'
        ' "instructions": string, "tool": {"name": string, "args": object}|null,'
        ' "transitions": [{"condition": string, "next": string}]}]}\n\n'
        f"Task: {task}\n"
        "Include clarification and error transitions. Do not execute tools."
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    try:
        parts = response.candidates[0].content.parts if response.candidates else []
    except Exception:
        parts = []
    full_text = "\n".join(p.text for p in parts or [] if getattr(p, "text", None))
    json_text = extract_json_text(full_text).strip()
    print(json_text)
    try:
        Path(slugify_filename(task)).write_text(json_text, encoding="utf-8")
    except OSError:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generic Gemini CLI (search/url/code tools + optional custom functions)"
    )
    parser.add_argument("prompt", nargs="?", help="Single query (omit for --chat)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model (default: {DEFAULT_MODEL})")
    parser.add_argument("--chat", action="store_true", help="Interactive chat")
    parser.add_argument(
        "--tools",
        default="search,url",
        help="Comma-separated built-in tools: search, url, code, all, none",
    )
    parser.add_argument("--plan", help="Write a JSON execution plan for this task")
    return parser.parse_args()


def main() -> None:
    load_env_files()
    args = parse_args()
    builtin_names = parse_tool_names(args.tools)

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    if args.plan:
        sys.exit(run_plan_mode(client, args.model, args.plan))

    if not args.prompt:
        args.chat = True

    if args.chat:
        asyncio.run(run_chat_loop_async(client, args.model, builtin_names))
        return

    asyncio.run(run_single_turn_async(client, args.model, args.prompt, builtin_names))


if __name__ == "__main__":
    main()
