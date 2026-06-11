def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "OK"


def test_score_claim(client, claim_payload):
    response = client.post("/api/v1/claims/score", json=claim_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["claim_id"] == claim_payload["claim_id"]
    assert "fraud_score" in body
    assert body["reasons"]


def test_batch_score(client, claim_payload):
    second = {**claim_payload, "claim_id": "CLM-10002", "claim_amount": 1200}
    response = client.post(
        "/api/v1/claims/batch-score",
        json={"claims": [claim_payload, second]},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_predict_without_files(client, claim_payload):
    response = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/predict-with-files",
        json=claim_payload,
    )
    assert response.status_code == 200
    assert response.json()["warnings"] == [
        "No documents or images were uploaded. Fraud score confidence is reduced."
    ]


def test_reused_identity_hash_is_detected(client, claim_payload):
    first = client.post("/api/v1/claims/score", json=claim_payload)
    assert first.status_code == 200
    second_claim = {**claim_payload, "claim_id": "CLM-IDENTITY-2"}
    second = client.post("/api/v1/claims/score", json=second_claim)
    assert second.status_code == 200
    codes = {item["code"] for item in second.json()["reasons"]}
    assert {"BANK_ACCOUNT_REUSED", "PHONE_REUSED", "EMAIL_REUSED"} <= codes
