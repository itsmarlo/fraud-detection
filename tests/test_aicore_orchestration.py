import json

from app.core.config import Settings
from app.models.file_schema import DocumentType
from app.services.aicore_orchestration_service import AICoreOrchestrationService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class RecordingHttpClient:
    def __init__(self):
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if url.endswith("/oauth/token"):
            return FakeResponse({"access_token": "token", "expires_in": 300})
        encoding = {
            "summary": "Visible bumper damage.",
            "detected_document_type": "DAMAGE_PHOTO",
            "confidence_score": 90,
            "evidence_risk_score": 25,
            "extracted_dates": [],
            "extracted_amounts": [],
            "document_numbers": [],
            "visual_observations": ["Bumper dent"],
            "inconsistencies": [],
            "suspicious_indicators": [],
            "damage_severity": "MODERATE",
            "description_consistency": "CONSISTENT",
        }
        return FakeResponse(
            {
                "orchestration_result": {
                    "choices": [{"message": {"content": json.dumps(encoding)}}]
                }
            }
        )


def settings(**overrides):
    values = {
        "enable_llm_encoder": True,
        "llm_provider": "btp",
        "aicore_token_url": "https://auth.example.com/oauth/token",
        "aicore_client_id": "client",
        "aicore_client_secret": "secret",
        "aicore_resource_group": "claims",
        "orch_deployment_url": (
            "https://api.example.com/v2/inference/deployments/orchestration"
        ),
        "aicore_llm_model": "gpt-4o",
        "masking_required": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_aicore_uses_oauth_resource_group_multimodal_and_masking(tmp_path):
    image_path = tmp_path / "damage.jpg"
    image_path.write_bytes(b"image")
    http_client = RecordingHttpClient()
    service = AICoreOrchestrationService(
        settings=settings(),
        http_client=http_client,
    )

    result = service.analyze(
        image_path,
        "image/jpeg",
        DocumentType.DAMAGE_PHOTO,
    )

    assert result.damage_severity == "MODERATE"
    token_url, token_request = http_client.requests[0]
    assert token_url == "https://auth.example.com/oauth/token"
    assert token_request["auth"] == ("client", "secret")

    completion_url, completion_request = http_client.requests[1]
    assert completion_url.endswith(
        "/v2/inference/deployments/orchestration/v2/completion"
    )
    assert completion_request["headers"]["AI-Resource-Group"] == "claims"
    modules = completion_request["json"]["config"]["modules"]
    content = modules["prompt_templating"]["prompt"]["template"][1]["content"]
    assert content[1]["type"] == "image_url"
    assert modules["masking"]["providers"][0]["mask_file_input_method"] == (
        "anonymization"
    )

    service.analyze(
        image_path,
        "image/jpeg",
        DocumentType.DAMAGE_PHOTO,
    )
    token_requests = [
        request for request in http_client.requests if request[0].endswith("/oauth/token")
    ]
    assert len(token_requests) == 1


def test_aicore_accepts_cloud_foundry_service_binding(monkeypatch):
    monkeypatch.delenv("AICORE_SERVICE_KEY", raising=False)
    monkeypatch.setenv(
        "VCAP_SERVICES",
        json.dumps(
            {
                "aicore": [
                    {
                        "credentials": {
                            "clientid": "bound-client",
                            "clientsecret": "bound-secret",
                            "url": "https://bound-auth.example.com",
                            "serviceurls": {
                                "AI_API_URL": "https://bound-api.example.com"
                            },
                        }
                    }
                ]
            }
        ),
    )
    service = AICoreOrchestrationService(
        settings=settings(
            aicore_token_url=None,
            aicore_client_id=None,
            aicore_client_secret=None,
        ),
        http_client=RecordingHttpClient(),
    )

    credentials = service._credentials()

    assert credentials["client_id"] == "bound-client"
    assert credentials["token_url"] == (
        "https://bound-auth.example.com/oauth/token"
    )
