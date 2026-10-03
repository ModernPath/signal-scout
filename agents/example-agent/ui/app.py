#!/usr/bin/env python3
"""
Flask web UI for Example Agent.

Run:
  python ui/app.py            # http://localhost:5012
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_llm  # noqa: E402
import example_service as service  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_chat import chat_reply  # noqa: E402
from memory.memory import NoteStore  # noqa: E402

load_agent_environment()

DEFAULT_PORT = 5012
USER_ERRORS = (ValueError, LookupError, service.SubagentError)


def create_app(store: Optional[NoteStore] = None) -> Flask:
    """App factory: pass a store to isolate tests from real data."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "example-agent-dev-secret")
    app.config["STORE"] = store or NoteStore()

    def current_store() -> NoteStore:
        return app.config["STORE"]

    @app.context_processor
    def inject_mode() -> dict:
        return {"llm_mode": agent_llm.model_name() if agent_llm.llm_available() else "offline"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def index():
        query = request.args.get("q", "").strip()
        tag = request.args.get("tag") or None
        return render_template(
            "index.html",
            notes=service.find_notes(current_store(), query, tag=tag, limit=None),
            overview=service.overview(current_store()),
            query=query,
            active_tag=tag,
        )

    @app.post("/notes")
    def create_note():
        try:
            note = service.add_note(
                current_store(),
                request.form.get("title", ""),
                request.form.get("body", ""),
                request.form.get("tags", ""),
            )
            flash(f"Saved “{note['title']}”.", "success")
        except USER_ERRORS as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/notes/<note_id>/delete")
    def delete_note(note_id: str):
        try:
            note = service.delete_note(current_store(), note_id)
            flash(f"Deleted “{note['title']}”.", "success")
        except USER_ERRORS as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/summary")
    def summarize():
        tag = request.form.get("tag") or None
        try:
            result = service.summarize_notes(current_store(), tag=tag)
            flash(result["summary"], "summary")
        except USER_ERRORS as exc:
            flash(str(exc), "error")
        return redirect(url_for("index", tag=tag))

    @app.get("/chat")
    def chat_page():
        return render_template("chat.html")

    @app.post("/api/chat")
    def api_chat():
        data = request.get_json(silent=True) or {}
        message = str(data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "Message is required."}), 400
        result = chat_reply(
            current_store(),
            message,
            history=data.get("history") or [],
            offline=bool(data.get("offline")),
        )
        return jsonify(
            reply=result.reply,
            history=result.history,
            used_llm=result.used_llm,
            tools_used=result.tools_used,
        )

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    create_app().run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
