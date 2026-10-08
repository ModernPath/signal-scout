from __future__ import annotations

import os

import pytest


def test_env_loaded_only_from_agent_folder(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import agent_env

    parent = tmp_path / "parent"
    agent = parent / "agent"
    agent.mkdir(parents=True)
    (parent / ".env").write_text("RL_PARENT_SECRET=leak\n")
    (parent / ".env.local").write_text("RL_PARENT_SECRET=leak\n")
    (agent / ".env").write_text("RL_AGENT_VALUE=ok\n")
    monkeypatch.delenv("RL_PARENT_SECRET", raising=False)
    monkeypatch.setattr(agent_env, "AGENT_DIR", agent)
    try:
        agent_env.load_agent_environment()
        assert os.environ.get("RL_AGENT_VALUE") == "ok"
        assert "RL_PARENT_SECRET" not in os.environ
    finally:
        os.environ.pop("RL_AGENT_VALUE", None)


def test_data_dir_override_redirects_store(isolated_env):
    from memory.memory import ReadingListStore

    assert ReadingListStore().data_dir == isolated_env
