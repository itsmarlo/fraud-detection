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
    workflow = body["joule_workflow"]
    assert workflow["claim_submission"]["policy_number"] == claim_payload["policy_id"]
    assert workflow["attachment_assessments"][0]["label"] == "Damaged Vehicle"
    assert workflow["claim_items"][0]["item_id"] == "0001"
    assert workflow["reserve_recommendation"]["recommended_reserve"] > 0
    assert "Approve adjusted reserve" in workflow["suggested_actions"][0]


def test_joule_workflow_matches_claim_prototype_values(client, claim_payload):
    claim = {
        **claim_payload,
        "claim_id": "5808",
        "policy_id": "ABX5678901",
        "policyholder_id": "Max Mustermann",
        "claim_amount": 1084,
        "accident_date": "2025-03-23",
        "claim_report_date": "2025-04-10",
        "accident_time_hour": 9,
        "accident_location": "Maximilianstrasse, Munich",
        "damage_description": "Collision with a tree trunk. Front bumper dented and windshield cracked.",
    }
    payload = {
        "claim": claim,
        "evidence": [
            {
                "filename": "damaged-vehicle.jpg",
                "content_type": "image/jpeg",
                "document_type": "DAMAGE_PHOTO",
                "content_base64": base64.b64encode(image_bytes()).decode("ascii"),
            },
            {
                "filename": "police-report.txt",
                "content_type": "text/plain",
                "document_type": "POLICE_REPORT",
                "content_base64": base64.b64encode(
                    b"Police report. Location: Maximilianstrasse, Munich."
                ).decode("ascii"),
            },
        ],
    }

    response = client.post("/api/v1/inference/fraud-assessment", json=payload)

    assert response.status_code == 200
    workflow = response.json()["joule_workflow"]
    assert workflow["claim_submission"]["policy_number"] == "ABX5678901"
    assert workflow["claim_submission"]["policyholder"] == "Max Mustermann"
    assert workflow["compensability"]["is_compensable"] is False
    assert "more than 10 days" in workflow["compensability"]["reason"]
    assert workflow["claim_items"][0]["amount"] == 1084
    assert workflow["reserve_recommendation"]["current_reserve"] == 794.57
    assert workflow["reserve_recommendation"]["recommended_reserve"] == 2350
    assert {item["label"] for item in workflow["attachment_assessments"]} == {
        "Damaged Vehicle",
        "Police report",
    }


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
