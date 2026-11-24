"""One real call to Gemini. Skipped by default; run with:  uv run pytest -m live"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.mark.live
@pytest.mark.skipif(not settings.gemini_api_key, reason="GEMINI_API_KEY not set")
def test_live_room_rent_question(client: TestClient) -> None:
    response = client.post(
        "/v1/ask",
        json={"question": "What is the room rent limit on my policy?"},
        headers={"X-API-Key": "demo-key-m001"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    print(body)
    assert "search_policy" in body["tools_used"]
    assert body["refused"] is False
    assert "3,000" in body["answer"]
    assert any(c["source_file"] == "sahay_basic.md" for c in body["citations"])
