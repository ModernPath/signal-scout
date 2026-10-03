from fastapi.testclient import TestClient
import subprocess
import sys
from pathlib import Path

from api.main import create_app
from test_service import service


def test_api_script_can_import_from_its_own_directory():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import runpy; runpy.run_path('api/main.py', run_name='api_probe')"],
        cwd=root, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_local_api_uses_shared_service_and_blocks_cross_origin_mutation(service):
    client = TestClient(create_app(service))
    assert client.get("/health").json()["status"] == "ok"
    denied = client.post("/analyze", json={"days": 30},
                         headers={"Origin": "http://evil.example"})
    assert denied.status_code == 403
    allowed = client.post("/analyze", json={"days": 30},
                          headers={"Origin": "http://testserver"})
    assert allowed.status_code == 200
    assert len(allowed.json()["opportunities"]) == 2
    assert client.get("/opportunities").json()["run_id"] == allowed.json()["run_id"]


def test_chat_api_persists_session_in_postgres(service):
    client = TestClient(create_app(service))
    response = client.post("/chat", json={"message": "list opportunities", "offline": True},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert len(client.get(f"/chat/{session_id}").json()["history"]) == 2


def test_api_can_clear_private_brief(service):
    client = TestClient(create_app(service))
    service.set_brief({"description": "Private position", "audience": "Leaders",
                       "expertise": "Security", "point_of_view": "Verify",
                       "voice": "Practical"})
    response = client.delete("/brief", headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert client.get("/brief").json() is None
