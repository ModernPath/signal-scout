"""Default development servers remain reachable only from this machine."""

import runpy

from flask import Flask

from conftest import AGENT_DIR


def test_api_and_ui_default_to_loopback(monkeypatch):
    monkeypatch.setattr("agent_env.load_agent_environment", lambda: None)
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    launches = []
    monkeypatch.setattr("uvicorn.run", lambda app, **options: launches.append(("api", options)))
    monkeypatch.setattr(
        Flask,
        "run",
        lambda self, **options: launches.append(("ui", options)),
    )

    runpy.run_path(str(AGENT_DIR / "api" / "main.py"), run_name="__main__")
    runpy.run_path(str(AGENT_DIR / "ui" / "app.py"), run_name="__main__")

    assert launches == [
        ("api", {"host": "127.0.0.1", "port": 8012}),
        ("ui", {"host": "127.0.0.1", "port": 5012, "debug": False}),
    ]
