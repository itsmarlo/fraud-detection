import base64
from io import BytesIO

from PIL import Image


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 600), color="red").save(output, format="JPEG")
    return output.getvalue()


def test_joule_friendly_inference_endpoint(client, claim_payload):
    payload = {
        "claim": {**claim_payload, "claim_id": "CLM-JOULE-1"},
        "evidence": [
            {
                "filename": "damage.jpg",
                "content_type": "image/jpeg",
                "document_type": "DAMAGE_PHOTO",
                "content_base64": base64.b64encode(image_bytes()).decode("ascii"),
            }
        ],
    }

    response = client.post("/api/v1/inference/fraud-assessment", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["claim_id"] == "CLM-JOULE-1"
    assert "fraud_score" in body
    assert "summary" in body
    assert body["evidence_used"][0]["document_type"] == "DAMAGE_PHOTO"
    assert isinstance(body["reasons"], list)


def test_inference_endpoint_rejects_invalid_base64(client, claim_payload):
    payload = {
        "claim": {**claim_payload, "claim_id": "CLM-JOULE-BAD"},
        "evidence": [
            {
                "filename": "damage.jpg",
                "content_type": "image/jpeg",
                "document_type": "DAMAGE_PHOTO",
                "content_base64": "not-base64",
            }
        ],
    }

    response = client.post("/api/v1/inference/fraud-assessment", json=payload)

    assert response.status_code == 422
    assert "Invalid base64 content" in response.json()["detail"]
