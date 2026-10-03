from test_service import service
from ui.app import create_app


def test_agent_dashboard_runs_analysis_and_shows_evidence(service):
    app = create_app(service)
    client = app.test_client()
    assert b"No opportunities yet" in client.get("/").data
    denied = client.post("/analyze", headers={"Origin": "http://evil.example"})
    assert denied.status_code == 403
    response = client.post("/analyze", headers={"Origin": "http://localhost"},
                           follow_redirects=True)
    assert response.status_code == 200
    assert b"Acme" in response.data
    assert b"Why now" in response.data
    assert b"Source evidence" in response.data


def test_agent_chat_page_uses_postgres_session(service):
    app = create_app(service)
    client = app.test_client()
    assert b"Ask about opportunities" in client.get("/chat").data
    result = client.post("/chat", data={"message": "list opportunities", "offline": "1"},
                         headers={"Origin": "http://localhost"}, follow_redirects=True)
    assert result.status_code == 200
    assert b"No opportunities yet" in result.data


def test_ui_can_clear_private_brief(service):
    service.set_brief({"description": "Private position", "audience": "Leaders",
                       "expertise": "Security", "point_of_view": "Verify",
                       "voice": "Practical"})
    client = create_app(service).test_client()
    assert b"Delete brief" in client.get("/").data
    response = client.post("/brief/delete", headers={"Origin": "http://localhost"},
                           follow_redirects=True)
    assert b"Company brief deleted" in response.data
    assert b"Private position" not in response.data
