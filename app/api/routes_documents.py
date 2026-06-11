from fastapi import APIRouter

from app.models.document_schema import (
    DocumentValidationResponse,
    ExtractedDocumentMetadata,
)
from app.services.document_validation_service import document_validation_service


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/validate", response_model=DocumentValidationResponse)
def validate_documents(
    metadata: ExtractedDocumentMetadata,
) -> DocumentValidationResponse:
    return document_validation_service.validate(metadata)
