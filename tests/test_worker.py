import os
import select
import signal
import subprocess
import sys

import psycopg
import pytest


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs disposable PostgreSQL")
def test_worker_stays_idle_and_exits_cleanly_without_provider_keys():
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
        if connection.execute("SELECT to_regclass('collection_run')").fetchone()[0]:
            connection.execute(
                "TRUNCATE collection_run, source_config, monitor_rule, "
                "monitor_profile RESTART IDENTITY CASCADE"
            )

    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"XAIGROK_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN"}
    }
    environment["DATABASE_URL"] = url
    worker = subprocess.Popen(
        [sys.executable, "-m", "signalscout.worker"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        readable, _, _ = select.select([worker.stdout], [], [], 5)
        assert readable, "worker did not report readiness"
        assert "Worker ready" in worker.stdout.readline()
        assert worker.poll() is None
        worker.send_signal(signal.SIGTERM)
        output, _ = worker.communicate(timeout=5)
        assert worker.returncode == 0
        assert "Worker stopped" in output
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.communicate(timeout=5)
