"""Count tokens across every model call in one agent turn.

The agent uses Gemini's automatic function calling: one chat message can make
several model calls (call a tool, read the result, answer). The SDK returns
usage for the last of them only, and every earlier call resent the whole
conversation, so reading `response.usage_metadata` would undercount cost badly.

This hook wraps the one SDK method each of those calls goes through and adds up
`usage_metadata`. It lives in evals/ rather than in the agent: it is a
measurement instrument, and the agent should not change to be measured.
`_generate_content` is a private SDK method, so `count_usage` fails loudly if
an SDK upgrade removes it instead of quietly reporting zero tokens.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    def add(self, metadata) -> None:
        self.calls += 1
        if metadata is None:
            return
        self.tokens_in += metadata.prompt_token_count or 0
        # Thinking tokens are billed as output on Gemini models that think.
        self.tokens_out += (metadata.candidates_token_count or 0) + (getattr(metadata, "thoughts_token_count", 0) or 0)


@contextmanager
def count_usage() -> Iterator[Usage]:
    from google.genai import models

    target = models.Models
    original = getattr(target, "_generate_content", None)
    if original is None:
        raise RuntimeError("google-genai no longer has Models._generate_content; update evals/usage.py")

    usage = Usage()

    def counted(self, *args, **kwargs):
        response = original(self, *args, **kwargs)
        usage.add(getattr(response, "usage_metadata", None))
        return response

    target._generate_content = counted
    try:
        yield usage
    finally:
        target._generate_content = original
