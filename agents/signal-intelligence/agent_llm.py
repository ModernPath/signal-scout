"""Optional Gemini chat client; imported only when model chat is selected."""

import os


def llm_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY")) and os.environ.get("SIGNAL_INTELLIGENCE_OFFLINE") != "1"


def model_name() -> str:
    return os.environ.get("SIGNAL_INTELLIGENCE_MODEL", "gemini-2.5-flash")


def get_client():
    if not llm_available():
        raise RuntimeError("Model provider is unavailable")
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("Install google-genai for model chat") from None
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
