from io import BytesIO

from PIL import Image
from pypdf import PdfWriter

from app.services.image_support import ai_image_payload
from app.services.file_storage_service import file_storage_service
from app.services.multimodal_encoder_service import multimodal_encoder_service


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 600), color="red").save(output, format="JPEG")
    return output.getvalue()


def image_bytes_for_format(image_format: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 600), color="blue").save(output, format=image_format)
    return output.getvalue()


def pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def test_upload_and_analyze_valid_image(client):
    upload = client.post(
        "/api/v1/claims/CLM-UPLOAD/files/upload",
        data={"document_type": "DAMAGE_PHOTO"},
        files={"files": ("damage.jpg", image_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201
    file_id = upload.json()[0]["file_id"]

    analysis = client.post(f"/api/v1/files/{file_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["analysis"]["width"] == 800
    assert analysis.json()["analysis"]["llm_encoder"]["status"] == "DISABLED"


def test_upload_multiple_images_in_one_request(client):
    response = client.post(
        "/api/v1/claims/CLM-MULTI-PHOTO/files/upload",
        data={"document_type": "DAMAGE_PHOTO"},
        files=[
            ("files", ("front.jpg", image_bytes(), "image/jpeg")),
            (
                "files",
                ("rear.png", image_bytes_for_format("PNG"), "image/png"),
            ),
        ],
    )

    assert response.status_code == 201
    assert len(response.json()) == 2
    assert {item["original_filename"] for item in response.json()} == {
        "front.jpg",
        "rear.png",
    }


def test_delete_claim_files_removes_metadata_and_binaries(client):
    upload = client.post(
        "/api/v1/claims/CLM-REPLACE/files/upload",
        data={"document_type": "DAMAGE_PHOTO"},
        files={"files": ("old.jpg", image_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201
    file_id = upload.json()[0]["file_id"]
    metadata = file_storage_service.metadata_service.get(file_id)
    stored_path = file_storage_service.path_for(metadata)
    assert stored_path.exists()

    response = client.delete("/api/v1/claims/CLM-REPLACE/files")

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    assert client.get("/api/v1/claims/CLM-REPLACE/files").json() == []
    assert not stored_path.exists()


def test_upload_and_analyze_iphone_heic_image(client):
    upload = client.post(
        "/api/v1/claims/CLM-IPHONE/files/upload",
        data={"document_type": "DAMAGE_PHOTO"},
        files={
            "files": (
                "IMG_1042.HEIC",
                image_bytes_for_format("HEIF"),
                "image/heic",
            )
        },
    )
    assert upload.status_code == 201
    file_id = upload.json()[0]["file_id"]

    analysis = client.post(f"/api/v1/files/{file_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["analysis"]["width"] == 800
    assert analysis.json()["analysis"]["format"] == "HEIF"


def test_upload_and_analyze_avif_image(client):
    upload = client.post(
        "/api/v1/claims/CLM-AVIF/files/upload",
        data={"document_type": "DAMAGE_PHOTO"},
        files={
            "files": (
                "damage.avif",
                image_bytes_for_format("AVIF"),
                "image/avif",
            )
        },
    )
    assert upload.status_code == 201
    file_id = upload.json()[0]["file_id"]

    analysis = client.post(f"/api/v1/files/{file_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["analysis"]["format"] == "AVIF"


def test_non_native_image_is_normalized_for_ai(tmp_path):
    image_path = tmp_path / "damage.tiff"
    image_path.write_bytes(image_bytes_for_format("TIFF"))

    payload, content_type = ai_image_payload(image_path, "image/tiff")

    assert content_type == "image/jpeg"
    with Image.open(BytesIO(payload)) as image:
        assert image.format == "JPEG"
        assert image.size == (800, 600)


def test_upload_and_analyze_valid_pdf(client):
    upload = client.post(
        "/api/v1/claims/CLM-PDF/files/upload",
        data={"document_type": "REPAIR_INVOICE"},
        files={"files": ("invoice.pdf", pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201
    file_id = upload.json()[0]["file_id"]
    analysis = client.post(f"/api/v1/files/{file_id}/analyze")
    assert analysis.status_code == 200
    assert "text_preview" in analysis.json()["analysis"]
    assert analysis.json()["analysis"]["llm_encoder"]["status"] == "DISABLED"


def test_reject_unsupported_file(client):
    response = client.post(
        "/api/v1/claims/CLM-BAD/files/upload",
        data={"document_type": "OTHER"},
        files={"files": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_reject_mime_extension_mismatch(client):
    response = client.post(
        "/api/v1/claims/CLM-MISMATCH/files/upload",
        data={"document_type": "OTHER"},
        files={"files": ("notes.txt", b"plain text", "application/pdf")},
    )
    assert response.status_code == 400


def test_reject_too_large_file(client):
    from app.services.file_storage_service import file_storage_service

    original = file_storage_service.settings.max_upload_size_mb
    file_storage_service.settings.max_upload_size_mb = 1
    try:
        response = client.post(
            "/api/v1/claims/CLM-LARGE/files/upload",
            data={"document_type": "OTHER"},
            files={"files": ("large.txt", b"a" * (1024 * 1024 + 1), "text/plain")},
        )
    finally:
        file_storage_service.settings.max_upload_size_mb = original
    assert response.status_code == 400


def test_predict_with_uploaded_files(client, claim_payload):
    for document_type, filename, content, mime in [
        ("DAMAGE_PHOTO", "damage.jpg", image_bytes(), "image/jpeg"),
        ("REPAIR_INVOICE", "invoice.pdf", pdf_bytes(), "application/pdf"),
    ]:
        response = client.post(
            f"/api/v1/claims/{claim_payload['claim_id']}/files/upload",
            data={"document_type": document_type},
            files={"files": (filename, content, mime)},
        )
        assert response.status_code == 201

    payload = {
        **claim_payload,
        "has_damage_photos": False,
        "has_repair_invoice": False,
    }
    prediction = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/predict-with-files",
        json=payload,
    )
    assert prediction.status_code == 200
    body = prediction.json()
    assert len(body["uploaded_files_used"]) == 2
    assert body["extraction_summary"]["images_processed"] == 1
    codes = {item["code"] for item in body["reasons"]}
    assert "NO_DAMAGE_PHOTOS" not in codes
    assert "NO_REPAIR_INVOICE" not in codes


def test_uploaded_police_report_overrides_stale_claim_flag(client, claim_payload):
    upload = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/files/upload",
        data={"document_type": "POLICE_REPORT"},
        files={"files": ("police-report.pdf", pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201

    payload = {**claim_payload, "has_police_report": False}
    prediction = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/predict-with-files",
        json=payload,
    )

    assert prediction.status_code == 200
    codes = {item["code"] for item in prediction.json()["reasons"]}
    assert "MISSING_POLICE_REPORT" not in codes


def test_missing_expected_documents_reduce_confidence(client, claim_payload):
    incomplete_claim = {**claim_payload, "claim_id": "CLM-INCOMPLETE"}
    complete_claim = {**claim_payload, "claim_id": "CLM-MORE-COMPLETE"}

    for claim_id in (incomplete_claim["claim_id"], complete_claim["claim_id"]):
        upload = client.post(
            f"/api/v1/claims/{claim_id}/files/upload",
            data={"document_type": "DAMAGE_PHOTO"},
            files={"files": ("damage.jpg", image_bytes(), "image/jpeg")},
        )
        assert upload.status_code == 201

    police_upload = client.post(
        f"/api/v1/claims/{complete_claim['claim_id']}/files/upload",
        data={"document_type": "POLICE_REPORT"},
        files={"files": ("police-report.pdf", pdf_bytes(), "application/pdf")},
    )
    assert police_upload.status_code == 201

    incomplete = client.post(
        f"/api/v1/claims/{incomplete_claim['claim_id']}/predict-with-files",
        json=incomplete_claim,
    ).json()
    more_complete = client.post(
        f"/api/v1/claims/{complete_claim['claim_id']}/predict-with-files",
        json=complete_claim,
    ).json()

    assert more_complete["confidence_score"] > incomplete["confidence_score"]
    assert any(
        "confidence is reduced" in warning.lower()
        for warning in incomplete["warnings"]
    )


def test_different_vehicle_comparison_affects_image_score(
    client,
    claim_payload,
    monkeypatch,
):
    for index, color in enumerate(("red", "blue"), start=1):
        output = BytesIO()
        Image.new("RGB", (800, 600), color=color).save(output, format="JPEG")
        response = client.post(
            f"/api/v1/claims/{claim_payload['claim_id']}/files/upload",
            data={"document_type": "DAMAGE_PHOTO"},
            files={
                "files": (
                    f"vehicle-{index}.jpg",
                    output.getvalue(),
                    "image/jpeg",
                )
            },
        )
        assert response.status_code == 201

    monkeypatch.setattr(
        multimodal_encoder_service,
        "compare_images",
        lambda images, claim: {
            "status": "COMPLETED",
            "vehicle_consistency": "INCONSISTENT",
            "confidence_score": 95,
            "distinct_vehicle_count": 2,
            "explanation": "The photographs show two different vehicles.",
            "findings": [
                {
                    "code": "DIFFERENT_VEHICLES_ACROSS_PHOTOS",
                    "message": "The photographs show two different vehicles.",
                    "severity": "VERY_HIGH",
                }
            ],
        },
    )

    prediction = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/predict-with-files",
        json=claim_payload,
    )

    assert prediction.status_code == 200
    body = prediction.json()
    assert body["image_score"] == 80
    assert "DIFFERENT_VEHICLES_ACROSS_PHOTOS" in {
        item["code"] for item in body["reasons"]
    }
