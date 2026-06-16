def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "OK"


def test_demo_ui_and_static_assets(client):
    root = client.get("/", follow_redirects=False)
    assert root.status_code in {302, 307}
    assert root.headers["location"] == "/demo"

    page = client.get("/demo")
    assert page.status_code == 200
    assert "SAP Fioneer" in page.text
    assert "Motor Claims Risk Assessment" in page.text
    assert 'id="claimForm"' in page.text
    assert "Required for assessment" in page.text
    assert "Add at least one image or document" in page.text
    assert "HEIC" not in page.text

    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert "predict-with-files" in script.text
    assert "queuedPhotos" in script.text
    assert "data-photo-index" in script.text
    assert "inferredDocumentType" in script.text
    assert "data-document-type-index" in script.text
    assert "Police report incl. witness statements" in page.text
    assert "WITNESS_STATEMENT" not in page.text
    assert 'id="ruleScore"' in page.text
    assert 'name="number_of_previous_claims" type="number" value="0"' in page.text
    assert 'name="premium_payment_status" value="CURRENT"' in page.text


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
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Upload at least one supporting image or document before assessment."
    )


def test_reused_identity_hash_is_detected(client, claim_payload):
    first = client.post("/api/v1/claims/score", json=claim_payload)
    assert first.status_code == 200
    second_claim = {**claim_payload, "claim_id": "CLM-IDENTITY-2"}
    second = client.post("/api/v1/claims/score", json=second_claim)
    assert second.status_code == 200
    codes = {item["code"] for item in second.json()["reasons"]}
    assert {"BANK_ACCOUNT_REUSED", "PHONE_REUSED", "EMAIL_REUSED"} <= codes
