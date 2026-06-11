from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentType(StrEnum):
    DAMAGE_PHOTO = "DAMAGE_PHOTO"
    REPAIR_INVOICE = "REPAIR_INVOICE"
    POLICE_REPORT = "POLICE_REPORT"
    ACCIDENT_REPORT = "ACCIDENT_REPORT"
    CLAIM_FORM = "CLAIM_FORM"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
    WITNESS_STATEMENT = "WITNESS_STATEMENT"
    OTHER = "OTHER"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    claim_id: str
    document_type: DocumentType
    original_filename: str
    stored_filename: str
    content_type: str
    file_size: int
    checksum: str
    upload_timestamp: datetime
    analysis_status: AnalysisStatus = AnalysisStatus.PENDING
    analysis_result: dict[str, Any] | None = None


class FilePublicMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    claim_id: str
    document_type: DocumentType
    original_filename: str
    content_type: str
    file_size: int
    checksum: str
    upload_timestamp: datetime
    analysis_status: AnalysisStatus
    analysis_result: dict[str, Any] | None = None


class FileAnalysisResponse(BaseModel):
    file_id: str
    claim_id: str
    document_type: DocumentType
    analysis_status: AnalysisStatus
    findings: list[dict[str, Any]]
    analysis: dict[str, Any]
