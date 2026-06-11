from io import BytesIO

from PIL import Image
from pypdf import PdfWriter


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 600), color="red").save(output, format="JPEG")
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

    prediction = client.post(
        f"/api/v1/claims/{claim_payload['claim_id']}/predict-with-files",
        json=claim_payload,
    )
    assert prediction.status_code == 200
    body = prediction.json()
    assert len(body["uploaded_files_used"]) == 2
    assert body["extraction_summary"]["images_processed"] == 1
