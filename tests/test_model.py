from app.models.claim_schema import ClaimInput
from app.services.model_service import model_service


def test_model_info_and_training(client):
    before = client.get("/api/v1/model/info")
    assert before.status_code == 200
    assert before.json()["available"] is False

    training = client.post("/api/v1/model/train")
    assert training.status_code == 200
    assert training.json()["training_samples"] >= 100

    after = client.get("/api/v1/model/info")
    assert after.status_code == 200
    assert after.json()["available"] is True
    assert after.json()["model_type"] == "CalibratedHistGradientBoostingClassifier"
    assert 0 <= after.json()["metrics"]["brier_score"] <= 1


def test_trained_model_returns_probability(client, claim_payload):
    training = client.post("/api/v1/model/train")
    assert training.status_code == 200
    assert training.json()["model_type"] == "CalibratedHistGradientBoostingClassifier"
    assert 0 <= training.json()["brier_score"] <= 1

    score = model_service.predict(ClaimInput.model_validate(claim_payload))
    assert score is not None
    assert 0 <= score <= 100
