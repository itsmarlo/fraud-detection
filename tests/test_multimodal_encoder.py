from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.models.claim_schema import ClaimInput
from app.models.encoder_schema import ImageSetConsistency, MultimodalEncoding
from app.models.file_schema import DocumentType
from app.services.multimodal_encoder_service import MultimodalEncoderService


class FakeResponses:
    def __init__(self, output: Any) -> None:
        self.output = output
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: Any) -> None:
        self.responses = FakeResponses(output)


class FailingResponses:
    def parse(self, **kwargs):
        raise TimeoutError("provider timeout")


class FailingClient:
    responses = FailingResponses()


def encoding(**overrides) -> MultimodalEncoding:
    values = {
        "summary": "Visible front bumper damage.",
        "detected_document_type": "DAMAGE_PHOTO",
        "confidence_score": 88,
        "evidence_risk_score": 20,
        "visual_observations": ["Front bumper is dented."],
    }
    values.update(overrides)
    return MultimodalEncoding.model_validate(values)


def claim() -> ClaimInput:
    return ClaimInput.model_validate(
        {
            "claim_id": "CLM-IMAGE-COMPARE",
            "policy_id": "POL-1",
            "policyholder_id": "CUST-1",
            "claim_amount": 5000,
            "vehicle_value": 15000,
            "repair_estimate_amount": 4500,
            "accident_date": "2026-05-10",
            "claim_report_date": "2026-05-11",
            "policy_start_date": "2025-01-01",
            "policy_end_date": "2027-01-01",
            "coverage_type": "COMPREHENSIVE",
            "driver_age": 35,
            "vehicle_age_years": 4,
            "vehicle_mileage": 50000,
            "number_of_previous_claims": 0,
            "number_of_previous_rejected_claims": 0,
            "premium_payment_status": "CURRENT",
            "recent_policy_change": False,
            "accident_location": "Berlin",
            "accident_time_hour": 12,
            "damage_description": "Front bumper damage.",
            "garage_id": "GAR-1",
            "garage_previous_suspicious_claims": 0,
            "has_police_report": True,
            "has_damage_photos": True,
            "has_repair_invoice": True,
            "has_witness_statement": False,
            "third_party_involved": False,
        }
    )


def test_encoder_is_disabled_by_default(tmp_path):
    image_path = tmp_path / "damage.jpg"
    image_path.write_bytes(b"image")
    service = MultimodalEncoderService(
        settings=Settings(enable_llm_encoder=False, llm_provider="openai")
    )

    result = service.analyze(
        image_path,
        "image/jpeg",
        DocumentType.DAMAGE_PHOTO,
    )

    assert result["status"] == "DISABLED"


def test_encoder_sends_image_and_returns_structured_result(tmp_path):
    image_path = tmp_path / "damage.jpg"
    image_path.write_bytes(b"image")
    client = FakeClient(encoding())
    service = MultimodalEncoderService(
        settings=Settings(
            enable_llm_encoder=True,
            llm_provider="openai",
            openai_api_key="test",
        ),
        client=client,
    )

    result = service.analyze(
        image_path,
        "image/jpeg",
        DocumentType.DAMAGE_PHOTO,
    )

    content = client.responses.request["input"][1]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert result["status"] == "COMPLETED"
    assert result["visual_observations"] == ["Front bumper is dented."]


def test_encoder_sends_document_as_file_input(tmp_path):
    document_path = tmp_path / "invoice.pdf"
    document_path.write_bytes(b"%PDF-test")
    client = FakeClient(encoding(detected_document_type="REPAIR_INVOICE"))
    service = MultimodalEncoderService(
        settings=Settings(
            enable_llm_encoder=True,
            llm_provider="openai",
            openai_api_key="test",
        ),
        client=client,
    )

    service.analyze(
        document_path,
        "application/pdf",
        DocumentType.REPAIR_INVOICE,
    )

    content = client.responses.request["input"][1]["content"]
    assert content[1]["type"] == "input_file"
    assert content[1]["filename"] == "invoice.pdf"
    assert content[1]["file_data"].startswith("data:application/pdf;base64,")


def test_encoder_converts_material_inconsistency_to_finding(tmp_path):
    image_path = tmp_path / "damage.jpg"
    image_path.write_bytes(b"image")
    client = FakeClient(
        encoding(
            evidence_risk_score=85,
            inconsistencies=["Damage location conflicts with the claim description."],
        )
    )
    service = MultimodalEncoderService(
        settings=Settings(
            enable_llm_encoder=True,
            llm_provider="openai",
            openai_api_key="test",
        ),
        client=client,
    )

    result = service.analyze(
        image_path,
        "image/jpeg",
        DocumentType.DAMAGE_PHOTO,
    )

    assert result["findings"][0]["code"] == "LLM_EVIDENCE_INCONSISTENCY"
    assert result["findings"][0]["severity"] == "VERY_HIGH"


def test_encoder_failure_returns_fallback_status(tmp_path):
    document_path = tmp_path / "invoice.pdf"
    document_path.write_bytes(b"%PDF-test")
    service = MultimodalEncoderService(
        settings=Settings(
            enable_llm_encoder=True,
            llm_provider="openai",
            openai_api_key="test",
        ),
        client=FailingClient(),
    )

    result = service.analyze(
        document_path,
        "application/pdf",
        DocumentType.REPAIR_INVOICE,
    )

    assert result["status"] == "FAILED"
    assert result["findings"] == []


def test_encoder_compares_multiple_images_and_flags_different_vehicles(tmp_path):
    first = tmp_path / "front.jpg"
    second = tmp_path / "rear.jpg"
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    client = FakeClient(
        ImageSetConsistency(
            vehicle_consistency="INCONSISTENT",
            confidence_score=94,
            distinct_vehicle_count=2,
            explanation="The photos show vehicles with different body colors and rear lights.",
            comparison_observations=["Different paint color", "Different rear-light shape"],
        )
    )
    service = MultimodalEncoderService(
        settings=Settings(
            enable_llm_encoder=True,
            llm_provider="openai",
            openai_api_key="test",
        ),
        client=client,
    )

    result = service.compare_images(
        [(first, "image/jpeg"), (second, "image/jpeg")],
        claim(),
    )

    content = client.responses.request["input"][1]["content"]
    assert [item["type"] for item in content] == [
        "input_text",
        "input_image",
        "input_image",
    ]
    assert result["status"] == "COMPLETED"
    assert result["findings"][0]["code"] == "DIFFERENT_VEHICLES_ACROSS_PHOTOS"
    assert result["findings"][0]["severity"] == "VERY_HIGH"
