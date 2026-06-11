def test_missing_documents_and_bad_dates(client):
    response = client.post(
        "/api/v1/documents/validate",
        json={
            "claim_id": "CLM-DOC",
            "accident_date": "2026-05-10",
            "claim_amount": 9000,
            "vehicle_value": 12000,
            "invoice_date": "2026-05-09",
            "photo_date": "2026-05-08",
            "repair_invoice_amount": 10000,
            "available_document_types": ["CLAIM_FORM"],
        },
    )
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["findings"]}
    assert "INVOICE_BEFORE_ACCIDENT" in codes
    assert "PHOTO_BEFORE_ACCIDENT" in codes
    assert "MISSING_DRIVER_LICENSE" in codes
    assert response.json()["document_score"] > 0
