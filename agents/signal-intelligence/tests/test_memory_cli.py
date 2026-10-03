import json
import os
import subprocess
import sys
from pathlib import Path

from test_service import service


def test_postgres_memory_inspection_cli(service):
    service.add_content({"title": "Prior article", "text": "Prior angle", "channel": "blog"})
    script = Path(__file__).resolve().parents[1] / "memory" / "memory.py"
    env = {**os.environ, "DATABASE_URL": os.environ["SIGNAL_INTELLIGENCE_TEST_DATABASE_URL"]}
    result = subprocess.run([sys.executable, str(script), "content"],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["data"][0]["title"] == "Prior article"
