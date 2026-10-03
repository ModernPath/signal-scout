import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs disposable PostgreSQL")
def test_migrations_are_repeatable_and_preserve_existing_data():
    url = os.environ["TEST_DATABASE_URL"]
    environment = {**os.environ, "DATABASE_URL": url}

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment, check=True)
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            revision = cursor.fetchone()[0]
            cursor.execute("CREATE TABLE IF NOT EXISTS core_test_marker (value integer NOT NULL)")
            cursor.execute("TRUNCATE core_test_marker")
            cursor.execute("INSERT INTO core_test_marker VALUES (42)")

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment, check=True)
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone()[0] == revision
            cursor.execute("SELECT value FROM core_test_marker")
            assert cursor.fetchall() == [(42,)]
