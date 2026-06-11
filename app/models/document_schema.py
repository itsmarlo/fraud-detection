from datetime import date

from pydantic import BaseModel, Field


class ExtractedDocumentMetadata(BaseModel):
    claim_id: str
    accident_date: date
    claim_amount: float = Field(ge=0)
    vehicle_value: float = Field(gt=0)
    invoice_date: date | None = None
    police_report_date: date | None = None
    photo_date: date | None = None
    repair_invoice_amount: float | None = Field(default=None, ge=0)
    available_document_types: list[str] = Field(default_factory=list)
    duplicate_checksums: list[str] = Field(default_factory=list)
    invoice_number: str | None = None
    invoice_used_by_claim_ids: list[str] = Field(default_factory=list)
    bank_detail_hash: str | None = None
    bank_detail_used_by_claim_ids: list[str] = Field(default_factory=list)
    high_value_threshold: float = 5000


class DocumentValidationResponse(BaseModel):
    document_score: float
    findings: list[dict]
    missing_documents: list[str]
