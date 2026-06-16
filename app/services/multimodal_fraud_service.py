from collections import Counter
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.risk_levels import RECOMMENDED_ACTIONS, RiskLevel, risk_level_for_score
from app.core.rules import reason
from app.core.scoring import score_structured_claim, structured_total
from app.models.claim_schema import ClaimInput
from app.models.document_schema import ExtractedDocumentMetadata
from app.models.file_schema import AnalysisStatus, DocumentType, FileMetadata
from app.models.scoring_schema import (
    ExtractionSummary,
    RiskReason,
    ScoringResponse,
    UploadedFileUsed,
)
from app.services.document_validation_service import (
    DocumentValidationService,
    document_validation_service,
)
from app.services.file_analysis_service import FileAnalysisService, file_analysis_service
from app.services.file_metadata_service import FileMetadataService, file_metadata_service
from app.services.model_service import ModelService, model_service
from app.services.network_risk_service import NetworkRiskService, network_risk_service
from app.services.score_fusion_service import ScoreFusionService, score_fusion_service


class MultimodalFraudService:
    def __init__(
        self,
        metadata_service: FileMetadataService | None = None,
        analysis_service: FileAnalysisService | None = None,
        validation_service: DocumentValidationService | None = None,
        network_service: NetworkRiskService | None = None,
        ml_service: ModelService | None = None,
        fusion_service: ScoreFusionService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.metadata_service = metadata_service or file_metadata_service
        self.analysis_service = analysis_service or file_analysis_service
        self.validation_service = validation_service or document_validation_service
        self.network_service = network_service or network_risk_service
        self.ml_service = ml_service or model_service
        self.fusion_service = fusion_service or score_fusion_service

    def score(self, claim: ClaimInput) -> ScoringResponse:
        files = self.metadata_service.list_for_claim(claim.claim_id)
        if not files:
            from app.services.fraud_scoring_service import fraud_scoring_service

            return fraud_scoring_service.score(claim)

        available_types = {file.document_type for file in files}
        claim = claim.model_copy(
            update={
                "has_damage_photos": DocumentType.DAMAGE_PHOTO in available_types,
                "has_repair_invoice": DocumentType.REPAIR_INVOICE in available_types,
                "has_police_report": DocumentType.POLICE_REPORT in available_types,
                "has_witness_statement": DocumentType.WITNESS_STATEMENT
                in available_types,
            }
        )
        analyzed_files = self._analyze_files(files, claim)
        structured_components, structured_findings = score_structured_claim(claim)
        structured_score = structured_total(structured_components)
        document_result = self.validation_service.validate(
            self._document_metadata(claim, analyzed_files)
        )
        document_files = [
            file
            for file in analyzed_files
            if file.document_type != DocumentType.DAMAGE_PHOTO
        ]
        document_score = self._blend_encoder_score(
            document_result.document_score,
            document_files,
        )
        image_comparison = self._compare_images(analyzed_files, claim)
        image_score, image_findings = self._image_score(
            analyzed_files,
            claim,
            image_comparison,
        )
        network_score, network_findings = self.network_service.score(claim, analyzed_files)
        document_findings = [
            RiskReason.model_validate(item) for item in document_result.findings
        ] + self._encoder_findings(document_files)
        rule_score = round(
            0.40 * structured_score
            + 0.25 * document_score
            + 0.20 * image_score
            + 0.15 * network_score,
            2,
        )
        ml_score = self.ml_service.predict(claim)
        final_score = self.fusion_service.combine(rule_score, ml_score)
        level = risk_level_for_score(final_score)
        summary = self._extraction_summary(analyzed_files)
        warnings = []
        if document_result.missing_documents:
            missing_count = len(document_result.missing_documents)
            warnings.append(
                "Assessment confidence is reduced because "
                f"{missing_count} expected evidence "
                f"{'type is' if missing_count == 1 else 'types are'} missing."
            )
        if not any(file.document_type == DocumentType.DAMAGE_PHOTO for file in analyzed_files):
            warnings.append("No damage images were uploaded. Image risk confidence is reduced.")
        image_count = sum(
            file.document_type == DocumentType.DAMAGE_PHOTO for file in analyzed_files
        )
        image_files = [
            file
            for file in analyzed_files
            if file.document_type == DocumentType.DAMAGE_PHOTO
        ]
        if image_files and not any(
            (file.analysis_result or {}).get("llm_encoder", {}).get("status")
            == AnalysisStatus.COMPLETED.value
            for file in image_files
        ):
            warnings.append(
                "Image AI analysis was unavailable. The imagery score uses local "
                "file and metadata checks only."
            )
        if image_count >= 2 and image_comparison.get("status") != "COMPLETED":
            warnings.append(
                "Cross-image vehicle consistency could not be evaluated."
            )
        return ScoringResponse(
            claim_id=claim.claim_id,
            fraud_score=final_score,
            risk_level=level,
            recommended_action=RECOMMENDED_ACTIONS[level],
            confidence_score=self._confidence(
                claim,
                summary,
                document_result.missing_documents,
            ),
            structured_claim_score=structured_score,
            document_score=document_score,
            image_score=image_score,
            network_score=network_score,
            rule_based_score=rule_score,
            ml_probability_score=ml_score,
            uploaded_files_used=[
                UploadedFileUsed(
                    file_id=file.file_id,
                    document_type=file.document_type,
                    filename=file.original_filename,
                    analysis_status=file.analysis_status,
                )
                for file in analyzed_files
            ],
            component_scores={
                "structured_claim_score": structured_score,
                "document_score": document_score,
                "image_score": image_score,
                "network_score": network_score,
            },
            reasons=[
                item for item in structured_findings if item.component != "network_risk"
            ] + document_findings + image_findings + network_findings,
            warnings=warnings,
            extraction_summary=summary,
            model_version=self.settings.model_version,
            timestamp=datetime.now(UTC),
        )

    def _analyze_files(
        self,
        files: list[FileMetadata],
        claim: ClaimInput,
    ) -> list[FileMetadata]:
        for file in files:
            try:
                self.analysis_service.analyze(
                    file.file_id,
                    accident_date=claim.accident_date,
                    claim=claim,
                )
            except ValueError:
                pass
        return self.metadata_service.list_for_claim(files[0].claim_id)

    def _document_metadata(
        self,
        claim: ClaimInput,
        files: list[FileMetadata],
    ) -> ExtractedDocumentMetadata:
        checksums = Counter(file.checksum for file in files)
        duplicate_checksums = [checksum for checksum, count in checksums.items() if count > 1]
        invoice_claim_ids: set[str] = set()
        bank_claim_ids: set[str] = set()
        repair_amounts: list[float] = []
        for file in files:
            result = file.analysis_result or {}
            if file.document_type == DocumentType.REPAIR_INVOICE:
                invoice_claim_ids.update(
                    self.metadata_service.claims_for_checksum(file.checksum, claim.claim_id)
                )
                repair_amounts.extend(
                    float(amount)
                    for amount in result.get("possible_amounts", [])
                    if 0 < float(amount) < claim.vehicle_value * 3
                )
                repair_amounts.extend(
                    float(amount)
                    for amount in result.get("llm_encoder", {}).get(
                        "extracted_amounts", []
                    )
                    if 0 < float(amount) < claim.vehicle_value * 3
                )
            bank_hash = result.get("bank_detail_hash")
            if bank_hash:
                for other in self.metadata_service.list_all():
                    if (
                        other.claim_id != claim.claim_id
                        and (other.analysis_result or {}).get("bank_detail_hash") == bank_hash
                    ):
                        bank_claim_ids.add(other.claim_id)

        return ExtractedDocumentMetadata(
            claim_id=claim.claim_id,
            accident_date=claim.accident_date,
            claim_amount=claim.claim_amount,
            vehicle_value=claim.vehicle_value,
            invoice_date=claim.invoice_date,
            photo_date=claim.photo_capture_date,
            repair_invoice_amount=max(repair_amounts) if repair_amounts else claim.repair_estimate_amount,
            available_document_types=[file.document_type.value for file in files],
            duplicate_checksums=duplicate_checksums,
            invoice_used_by_claim_ids=sorted(invoice_claim_ids),
            bank_detail_used_by_claim_ids=sorted(bank_claim_ids),
            high_value_threshold=self.settings.approval_threshold_1,
        )

    def _compare_images(
        self,
        files: list[FileMetadata],
        claim: ClaimInput,
    ) -> dict:
        image_files = [
            file for file in files if file.document_type == DocumentType.DAMAGE_PHOTO
        ]
        images = [
            (
                self.analysis_service.storage_service.path_for(file),
                file.content_type,
            )
            for file in image_files
        ]
        return self.analysis_service.encoder_service.compare_images(images, claim)

    @staticmethod
    def _image_score(
        files: list[FileMetadata],
        claim: ClaimInput,
        image_comparison: dict | None = None,
    ) -> tuple[float, list[RiskReason]]:
        image_files = [file for file in files if file.document_type == DocumentType.DAMAGE_PHOTO]
        findings: list[RiskReason] = []
        score = 0.0
        code_points = {
            "LOW_RESOLUTION_IMAGE": 25,
            "PHOTO_BEFORE_ACCIDENT": 70,
            "DUPLICATE_IMAGE_ACROSS_CLAIMS": 80,
            "FILE_ANALYSIS_FAILED": 30,
            "LLM_EVIDENCE_INCONSISTENCY": 45,
            "DIFFERENT_VEHICLES_ACROSS_PHOTOS": 80,
        }
        for file in image_files:
            for item in (file.analysis_result or {}).get("findings", []):
                parsed = RiskReason.model_validate(item)
                findings.append(parsed)
                score += code_points.get(parsed.code, 15)
        if claim.claim_amount >= 5000 and len(image_files) < 2:
            score += 25
            findings.append(
                reason(
                    "TOO_FEW_DAMAGE_PHOTOS",
                    "Fewer than two damage photos were provided for a high-value claim.",
                    RiskLevel.MEDIUM,
                    25,
                    "image",
                )
            )
        if not image_files:
            score += 35
            findings.append(
                reason(
                    "MISSING_DAMAGE_PHOTOS",
                    "No uploaded damage photos are available for analysis.",
                    RiskLevel.HIGH,
                    35,
                    "image",
                )
            )
        blended_score = MultimodalFraudService._blend_encoder_score(
            min(100.0, score),
            image_files,
        )
        comparison_score = 0.0
        for item in (image_comparison or {}).get("findings", []):
            parsed = RiskReason.model_validate(item)
            findings.append(parsed)
            comparison_score = max(
                comparison_score,
                code_points.get(parsed.code, 15),
            )
        return max(blended_score, comparison_score), findings

    @staticmethod
    def _encoder_findings(files: list[FileMetadata]) -> list[RiskReason]:
        findings = []
        for file in files:
            for item in (file.analysis_result or {}).get("llm_encoder", {}).get(
                "findings", []
            ):
                findings.append(RiskReason.model_validate(item))
        return findings

    @staticmethod
    def _blend_encoder_score(
        deterministic_score: float,
        files: list[FileMetadata],
    ) -> float:
        encoder_scores = [
            float(encoding["evidence_risk_score"])
            for file in files
            if (encoding := (file.analysis_result or {}).get("llm_encoder", {})).get(
                "status"
            )
            == "COMPLETED"
        ]
        if not encoder_scores:
            return round(deterministic_score, 2)
        encoder_score = max(encoder_scores)
        return round(0.75 * deterministic_score + 0.25 * encoder_score, 2)

    @staticmethod
    def _extraction_summary(files: list[FileMetadata]) -> ExtractionSummary:
        images = [file for file in files if file.document_type == DocumentType.DAMAGE_PHOTO]
        documents = [file for file in files if file.document_type != DocumentType.DAMAGE_PHOTO]
        return ExtractionSummary(
            documents_processed=len(documents),
            images_processed=len(images),
            text_extraction_successful=sum(
                bool((file.analysis_result or {}).get("extraction_successful"))
                for file in documents
            ),
            image_metadata_extracted=sum(
                bool((file.analysis_result or {}).get("metadata_extracted"))
                for file in images
            ),
            llm_files_encoded=sum(
                (file.analysis_result or {}).get("llm_encoder", {}).get("status")
                == "COMPLETED"
                for file in files
            ),
        )

    @staticmethod
    def _confidence(
        claim: ClaimInput,
        summary: ExtractionSummary,
        missing_documents: list[str],
    ) -> float:
        required_count = 5
        if claim.claim_amount >= get_settings().approval_threshold_1:
            required_count += 1
        present_required_count = max(0, required_count - len(missing_documents))
        completeness = present_required_count / required_count

        score = 35.0
        score += 45 * completeness
        score += min(6, summary.text_extraction_successful * 2)
        score += min(6, summary.image_metadata_extracted * 3)
        score += min(8, summary.llm_files_encoded * 2)
        return min(100.0, round(score, 2))


multimodal_fraud_service = MultimodalFraudService()
