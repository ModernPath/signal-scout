"""The served app exposes the three functional screens and API client."""

from fastapi.testclient import TestClient

from signalscout.config import Settings
from signalscout.web import create_app


def test_root_serves_live_feature_screens_without_prototype_data():
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))
    client = TestClient(app, base_url="http://localhost")

    page = client.get("/")
    script = client.get("/app.js")

    assert page.status_code == script.status_code == 200
    assert all(label in page.text for label in ("Signal feed", "Monitoring", "Collection"))
    assert 'src="/app.js?v=' in page.text
    assert page.headers["cache-control"] == "no-store"
    assert script.headers["cache-control"] == "no-store"
    assert "Sample data" not in page.text
    assert "sample signals" not in page.text
    assert "const signals = [" not in page.text
    assert "fetch(" in script.text


def test_main_shell_exposes_intelligence_workflow():
    client=TestClient(create_app(Settings('postgresql+psycopg://scout:secret@localhost:5432/signalscout')),
                      base_url='http://localhost')
    page=client.get('/')
    assert 'data-view="opportunities"' in page.text
    assert 'data-view="company"' in page.text
    assert 'id="opportunities-view"' in page.text
    assert 'id="company-brief-form"' in page.text
    script=client.get('/intelligence.js')
    assert script.status_code==200
    assert script.headers['cache-control']=='no-store'
    assert 'src="/intelligence.js?v=' in page.text
