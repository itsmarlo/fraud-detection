from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.file_schema import (
    DocumentType,
    FileAnalysisResponse,
    FilePublicMetadata,
)
from app.services.file_analysis_service import file_analysis_service
from app.services.file_metadata_service import file_metadata_service
from app.services.file_storage_service import FileValidationError, file_storage_service


router = APIRouter(prefix="/api/v1", tags=["files"])


@router.post(
    "/claims/{claim_id}/files/upload",
    response_model=list[FilePublicMetadata],
    status_code=status.HTTP_201_CREATED,
)
async def upload_claim_files(
    claim_id: str,
    document_type: Annotated[DocumentType, Form()],
    files: Annotated[list[UploadFile], File()],
) -> list[FilePublicMetadata]:
    uploaded = []
    for upload in files:
        try:
            metadata = await file_storage_service.store(claim_id, document_type, upload)
            uploaded.append(FilePublicMetadata.model_validate(metadata))
        except FileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return uploaded


@router.get(
    "/claims/{claim_id}/files",
    response_model=list[FilePublicMetadata],
)
def list_claim_files(claim_id: str) -> list[FilePublicMetadata]:
    return [
        FilePublicMetadata.model_validate(file)
        for file in file_metadata_service.list_for_claim(claim_id)
    ]


@router.post("/files/{file_id}/analyze", response_model=FileAnalysisResponse)
def analyze_file(file_id: str) -> FileAnalysisResponse:
    try:
        return file_analysis_service.analyze(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="Stored file is no longer available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
