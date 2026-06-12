from types import SimpleNamespace

from app.core.config import Settings
from app.models.encoder_schema import MultimodalEncoding
from app.models.file_schema import DocumentType
from app.services.multimodal_encoder_service import MultimodalEncoderService


class FakeResponses:
    def __init__(self, output: MultimodalEncoding) -> None:
        self.output = output
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: MultimodalEncoding) -> None:
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
