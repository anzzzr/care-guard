from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_web_ui_is_served() -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "CareGuard" in page.text
    assert client.get("/static/app.js").status_code == 200
