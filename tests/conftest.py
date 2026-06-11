import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.file_metadata_service import file_metadata_service
from app.services.file_storage_service import file_storage_service
from app.services.model_service import model_service


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path):
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text(
        json.dumps({"files": [], "claim_identities": []}),
        encoding="utf-8",
    )
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    file_metadata_service.metadata_file = metadata_file
    file_storage_service.upload_dir = upload_dir
    model_service.model_path = tmp_path / "model.pkl"
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def claim_payload():
    return {
        "claim_id": "CLM-10001",
        "policy_id": "POL-20001",
        "policyholder_id": "CUST-30001",
        "claim_amount": 8200,
        "vehicle_value": 15000,
        "repair_estimate_amount": 7800,
        "accident_date": "2026-05-10",
        "claim_report_date": "2026-05-20",
        "policy_start_date": "2026-05-01",
        "policy_end_date": "2027-04-30",
        "coverage_type": "COMPREHENSIVE",
        "driver_age": 27,
        "vehicle_age_years": 6,
        "vehicle_mileage": 92000,
        "number_of_previous_claims": 4,
        "number_of_previous_rejected_claims": 1,
        "premium_payment_status": "OVERDUE",
        "recent_policy_change": True,
        "accident_location": "Berlin",
        "accident_time_hour": 2,
        "damage_description": "Front bumper and left headlamp damaged after collision.",
        "garage_id": "GAR-009",
        "garage_previous_suspicious_claims": 6,
        "has_police_report": False,
        "has_damage_photos": True,
        "has_repair_invoice": True,
        "has_witness_statement": False,
        "invoice_date": "2026-05-11",
        "photo_capture_date": "2026-05-10",
        "bank_account_hash": "bank-a",
        "phone_hash": "phone-a",
        "email_hash": "email-a",
        "third_party_involved": True,
    }
