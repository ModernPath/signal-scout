"""Server-rendered local dashboard and chat for the independent agent."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_env import make_service  # noqa: E402
from intelligence_chat import chat_reply  # noqa: E402
from intelligence_service import public_url  # noqa: E402


def create_app(service=None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("AGENT_FLASK_SECRET") or secrets.token_hex(32)
    app.config["SERVICE"] = service

    def current_service():
        if app.config["SERVICE"] is None:
            app.config["SERVICE"] = make_service()
        return app.config["SERVICE"]

    @app.before_request
    def same_origin():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            fetch_site = request.headers.get("Sec-Fetch-Site")
            expected = request.host_url.rstrip("/")
            if ((origin is None and fetch_site != "same-origin") or
                    (origin is not None and origin != expected) or
                    fetch_site not in (None, "same-origin")):
                abort(403)

    @app.context_processor
    def inject_helpers():
        return {"public_url": public_url}

    @app.get("/health")
    def health():
        current_service().store.check_schema()
        return {"status": "ok"}

    @app.get("/")
    def index():
        agent = current_service()
        result = agent.opportunities()
        items = result["opportunities"]
        selected_id = request.args.get("opportunity", type=int) or (items[0]["id"] if items else None)
        selected = agent.opportunity_detail(selected_id) if selected_id else None
        return render_template("index.html", opportunities=items, selected=selected,
                               run_id=result["run_id"], brief=agent.get_brief(),
                               content=agent.list_content(),knowledge=agent.knowledge.status())

    def safe_action(action, success: str, destination: str = "index", **values):
        try:
            action()
            flash(success, "success")
        except (ValueError, LookupError, RuntimeError) as exc:
            flash(str(exc), "error")
        return redirect(url_for(destination, **values))

    @app.post('/knowledge/index')
    def index_knowledge():
        def index():
            agent=current_service();agent.knowledge.store.retry();agent.knowledge.index_pending()
        return safe_action(index,'Knowledge indexing batch completed.')

    @app.post('/knowledge/search')
    def search_knowledge():
        try:
            result=current_service().search_knowledge(request.form.get('query',''))
            return render_template('knowledge.html',retrieval=result)
        except (ValueError,RuntimeError) as exc:
            flash(str(exc),'error')
            return redirect(url_for('index'))

    @app.post('/refine/<int:opportunity_id>')
    def refine_angle(opportunity_id):
        return safe_action(lambda:current_service().refine_angle(opportunity_id),'Angle refined; review sources.',opportunity=opportunity_id)

    @app.post("/brief")
    def set_brief():
        fields = ("description", "audience", "expertise", "point_of_view", "voice", "avoid_claims")
        return safe_action(lambda: current_service().set_brief(
            {key: request.form.get(key, "") for key in fields}), "Company brief saved.")

    @app.post("/brief/delete")
    def clear_brief():
        return safe_action(lambda: current_service().clear_brief(), "Company brief deleted.")

    @app.post("/content")
    def add_content():
        return safe_action(lambda: current_service().add_content({
            "title": request.form.get("title", ""), "text": request.form.get("text", ""),
            "channel": request.form.get("channel", ""), "url": request.form.get("url") or None}),
            "Previous content added.")

    @app.route("/content/<int:content_id>/edit", methods=["GET", "POST"])
    def edit_content(content_id: int):
        agent = current_service()
        if request.method == "POST":
            return safe_action(lambda: agent.replace_content(content_id, {
                "title": request.form.get("title", ""), "text": request.form.get("text", ""),
                "channel": request.form.get("channel", ""), "url": request.form.get("url") or None}),
                "Previous content replaced.")
        item = next((row for row in agent.list_content() if row["id"] == content_id), None)
        if item is None:
            abort(404)
        return render_template("content_edit.html", item=item)

    @app.post("/content/<int:content_id>/delete")
    def delete_content(content_id: int):
        return safe_action(lambda: current_service().delete_content(content_id),
                           "Previous content deleted.")

    @app.post("/analyze")
    def analyze():
        return safe_action(lambda: current_service().analyze(
            days=int(request.form.get("days", "30"))), "Analysis complete.")

    @app.post("/opportunities/<int:opportunity_id>/research")
    def research(opportunity_id: int):
        return safe_action(lambda: current_service().research(opportunity_id),
                           "Research saved for review.", opportunity=opportunity_id)

    @app.post("/opportunities/<int:opportunity_id>/draft")
    def draft(opportunity_id: int):
        return safe_action(lambda: current_service().draft(
            opportunity_id, request.form.get("channel", ""),
            request.form.get("format", "")), "Draft saved for review.",
            opportunity=opportunity_id)

    @app.route("/chat", methods=["GET", "POST"])
    def chat():
        agent = current_service()
        if request.method == "POST":
            try:
                result = chat_reply(agent, request.form.get("message", ""),
                                    session_id=session.get("chat_id"),
                                    offline=bool(request.form.get("offline")))
                session["chat_id"] = result.session_id
            except (ValueError, LookupError, RuntimeError) as exc:
                flash(str(exc), "error")
            return redirect(url_for("chat"))
        try:
            history = agent.chat_history(session["chat_id"]) if session.get("chat_id") else []
        except LookupError:
            session.pop("chat_id", None)
            history = []
        return render_template("chat.html", history=history)

    @app.post("/chat/reset")
    def reset_chat():
        if session.get("chat_id"):
            try:
                current_service().delete_chat_session(session["chat_id"])
            except LookupError:
                pass
        session.pop("chat_id", None)
        return redirect(url_for("chat"))

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("AGENT_BIND_HOST", "127.0.0.1"),
                     port=int(os.environ.get("AGENT_UI_PORT", "5013")), debug=False)
