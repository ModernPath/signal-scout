import json
import os
import subprocess
import sys
from pathlib import Path

from test_service import service  # Reuse the disposable PostgreSQL fixture.

AGENT_DIR = Path(__file__).resolve().parents[1]


def test_direct_analysis_tool_returns_json_contract(service):
    env = {**os.environ, "DATABASE_URL": os.environ["SIGNAL_INTELLIGENCE_TEST_DATABASE_URL"]}
    result = subprocess.run([sys.executable, str(AGENT_DIR / "tools" / "analyze_signals.py"),
                             "--days", "30"], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert len(payload["data"]["opportunities"]) == 2
