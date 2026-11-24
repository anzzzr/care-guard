from fastapi.testclient import TestClient


def test_missing_api_key_is_rejected(client: TestClient) -> None:
    assert client.get("/v1/claims").status_code == 401


def test_unknown_api_key_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/claims", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


def test_member_sees_only_their_own_claims(client: TestClient) -> None:
    response = client.get("/v1/claims", headers={"X-API-Key": "demo-key-m001"})
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()}
    assert ids == {"CLM-1001", "CLM-1002", "CLM-1003"}


def test_two_members_never_share_claims(client: TestClient) -> None:
    a = client.get("/v1/claims", headers={"X-API-Key": "demo-key-m001"}).json()
    b = client.get("/v1/claims", headers={"X-API-Key": "demo-key-m006"}).json()
    assert a and b
    assert not {c["id"] for c in a} & {c["id"] for c in b}


def test_claim_fields_are_returned(client: TestClient) -> None:
    claims = client.get("/v1/claims", headers={"X-API-Key": "demo-key-m001"}).json()
    dengue = next(c for c in claims if c["id"] == "CLM-1003")
    assert dengue["status"] == "partially_approved"
    assert dengue["amount_claimed"] == 60000
    assert dengue["amount_approved"] == 42000
    assert "Section 3.2" in dengue["rejection_reason"]
    assert "api_key" not in dengue
