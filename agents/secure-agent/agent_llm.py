"""Gemini client helpers shared by the main agent and subagents."""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_MODEL = "gemini-3.8-flash"
API_KEY_VARS = ("GOOGLE_AI_STUDIO_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
OFFLINE_ENV = "SECURE_AGENT_OFFLINE"
MODEL_ENV = "SECURE_AGENT_MODEL"
# Every model request gives up after this long, so a stuck call cannot hold a
# turn (and its cost) open indefinitely.
REQUEST_TIMEOUT_MS = 30_000


def model_name() -> str:
    return os.environ.get(MODEL_ENV, DEFAULT_MODEL)


def load_api_key() -> Optional[str]:
    return next((os.environ[var] for var in API_KEY_VARS if os.environ.get(var)), None)


def llm_available() -> bool:
    """True when a key is set and SECURE_AGENT_OFFLINE=1 has not forced offline mode."""
    return os.environ.get(OFFLINE_ENV) != "1" and load_api_key() is not None


def get_client():
    """Return a Gemini client with a request timeout. Imported lazily so offline mode needs no SDK."""
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError(f"No Gemini API key set (tried {', '.join(API_KEY_VARS)}).")
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))


def generate_text(prompt: str, *, system: Optional[str] = None) -> str:
    """Single-shot text generation without tools."""
    from google.genai import types

    client = get_client()  # keep referenced: the SDK closes its connection on garbage collection
    response = client.models.generate_content(
        model=model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return (response.text or "").strip()
