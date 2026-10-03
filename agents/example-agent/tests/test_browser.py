"""Real-browser journeys against a live Flask UI (the AGENTS.md loop-end gate).

Skipped when Playwright is not installed:
  pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from typing import Iterator

import pytest
import requests

from conftest import AGENT_DIR

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server_url() -> Iterator[str]:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(AGENT_DIR / "ui" / "app.py")],
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if proc.poll() is not None:
                pytest.fail(f"UI exited early: {proc.stderr.read().decode()}")
            try:
                if requests.get(f"{url}/health", timeout=0.5).ok:
                    break
            except requests.ConnectionError:
                time.sleep(0.1)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def page(server_url: str):
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(base_url=server_url)
        yield page
        browser.close()


def test_notes_journey(page):
    page.goto("/")
    sync_api.expect(page.get_by_text("No notes yet")).to_be_visible()

    page.fill("#title", "Call Bob")
    page.fill("#tags", "work")
    page.click("#note-form button[type=submit]")
    sync_api.expect(page.get_by_text("Saved “Call Bob”.")).to_be_visible()

    page.click("text=#work · 1")
    page.click("#summarize-btn")
    sync_api.expect(page.locator(".flash.summary")).to_contain_text("1 note(s).")

    page.click("button[aria-label='Delete Call Bob']")
    sync_api.expect(page.get_by_text("Deleted “Call Bob”.")).to_be_visible()


def test_empty_title_blocked_by_browser_validation(page):
    page.goto("/")
    page.click("#note-form button[type=submit]")
    assert page.eval_on_selector("#title", "el => !el.validity.valid")
    sync_api.expect(page.get_by_text("Saved")).to_have_count(0)


def test_chat_journey(page):
    page.goto("/chat")
    page.fill("#chat-input", "add Buy oat milk #shopping")
    page.press("#chat-input", "Enter")
    sync_api.expect(page.locator(".bubble.agent").last).to_contain_text("tools: add_note")

    page.fill("#chat-input", "list notes")
    page.press("#chat-input", "Enter")
    sync_api.expect(page.locator(".bubble.agent").last).to_contain_text("Buy oat milk")
