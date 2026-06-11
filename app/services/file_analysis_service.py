from datetime import date
from pathlib import Path
from typing import Any

from app.models.claim_schema import ClaimInput
from app.models.file_schema import AnalysisStatus, FileAnalysisResponse
from app.services.document_extraction_service import (
    DocumentExtractionService,
    document_extraction_service,
)
from app.services.file_metadata_service import FileMetadataService, file_metadata_service
from app.services.file_storage_service import FileStorageService, file_storage_service
from app.services.image_analysis_service import ImageAnalysisService, image_analysis_service
from app.services.multimodal_encoder_service import (
    MultimodalEncoderService,
    multimodal_encoder_service,
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class FileAnalysisService:
    def __init__(
        self,
        metadata_service: FileMetadataService | None = None,
        storage_service: FileStorageService | None = None,
        document_service: DocumentExtractionService | None = None,
        image_service: ImageAnalysisService | None = None,
        encoder_service: MultimodalEncoderService | None = None,
    ) -> None:
        self.metadata_service = metadata_service or file_metadata_service
        self.storage_service = storage_service or file_storage_service
        self.document_service = document_service or document_extraction_service
        self.image_service = image_service or image_analysis_service
        self.encoder_service = encoder_service or multimodal_encoder_service

    def analyze(
        self,
        file_id: str,
        accident_date: date | None = None,
        claim: ClaimInput | None = None,
    ) -> FileAnalysisResponse:
        metadata = self.metadata_service.get(file_id)
        if not metadata:
            raise KeyError(file_id)
        file_path = self.storage_service.path_for(metadata)
        if not file_path.exists():
            raise FileNotFoundError(file_id)

        try:
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                duplicate_claims = self.metadata_service.claims_for_checksum(
                    metadata.checksum,
                    metadata.claim_id,
                )
                analysis = self.image_service.analyze(
                    file_path,
                    accident_date=accident_date,
                    duplicate_claim_ids=duplicate_claims,
                )
            else:
                analysis = self.document_service.extract(file_path)
                analysis["findings"] = self._document_findings(metadata.checksum, metadata.claim_id)
            llm_encoding = self.encoder_service.analyze(
                file_path=file_path,
                content_type=metadata.content_type,
                document_type=metadata.document_type,
                claim=claim,
            )
            analysis["llm_encoder"] = llm_encoding
            analysis["findings"] = analysis.get("findings", []) + llm_encoding.get(
                "findings", []
            )
            findings = analysis.get("findings", [])
            updated = self.metadata_service.update_analysis(
                file_id,
                AnalysisStatus.COMPLETED,
                analysis,
            )
            return FileAnalysisResponse(
                file_id=updated.file_id,
                claim_id=updated.claim_id,
                document_type=updated.document_type,
                analysis_status=updated.analysis_status,
                findings=findings,
                analysis=analysis,
            )
        except Exception as exc:
            result: dict[str, Any] = {
                "error": str(exc),
                "findings": [
                    {
                        "code": "FILE_ANALYSIS_FAILED",
                        "message": "The uploaded file could not be analyzed.",
                        "severity": "HIGH",
                    }
                ],
            }
            self.metadata_service.update_analysis(file_id, AnalysisStatus.FAILED, result)
            raise ValueError(f"File analysis failed: {exc}") from exc

    def _document_findings(self, checksum: str, claim_id: str) -> list[dict[str, str]]:
        duplicate_claims = self.metadata_service.claims_for_checksum(checksum, claim_id)
        if not duplicate_claims:
            return []
        return [
            {
                "code": "DUPLICATE_DOCUMENT_ACROSS_CLAIMS",
                "message": f"Identical document is associated with claims: {', '.join(duplicate_claims)}.",
                "severity": "VERY_HIGH",
            }
        ]


file_analysis_service = FileAnalysisService()
