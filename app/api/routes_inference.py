import base64
from binascii import Error as Base64Error
from io import BytesIO

from fastapi import APIRouter, HTTPException
from starlette.datastructures import Headers, UploadFile

from app.models.inference_schema import (
    FraudAssessmentRequest,
    FraudAssessmentResponse,
    JouleEvidenceUsed,
    JouleFinding,
)
from app.services.file_storage_service import FileValidationError, file_storage_service
from app.services.multimodal_fraud_service import multimodal_fraud_service


router = APIRouter(prefix="/api/v1/inference", tags=["inference"])


@router.post("/fraud-assessment", response_model=FraudAssessmentResponse)
async def fraud_assessment(
    payload: FraudAssessmentRequest,
) -> FraudAssessmentResponse:
    claim = payload.claim
    if payload.replace_existing_evidence:
        file_storage_service.remove_for_claim(claim.claim_id)

    for evidence in payload.evidence:
        try:
            content = base64.b64decode(evidence.content_base64, validate=True)
        except (Base64Error, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid base64 content for {evidence.filename}",
            ) from exc
        upload = UploadFile(
            file=BytesIO(content),
            filename=evidence.filename,
            headers=Headers({"content-type": evidence.content_type}),
        )
        try:
            await file_storage_service.store(
                claim.claim_id,
                evidence.document_type,
                upload,
            )
        except FileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload.evidence and not file_storage_service.metadata_service.list_for_claim(
        claim.claim_id
    ):
        raise HTTPException(
            status_code=422,
            detail="Provide at least one evidence item for AI Core/Joule assessment.",
        )

    result = multimodal_fraud_service.score(claim)
    return FraudAssessmentResponse(
        claim_id=result.claim_id,
        fraud_score=result.fraud_score,
        risk_level=result.risk_level.value,
        confidence_score=result.confidence_score,
        recommended_action=result.recommended_action,
        summary=(
            f"{result.risk_level.value.replace('_', ' ').title()} risk assessment "
            f"with {result.confidence_score:.0f}% confidence. "
            f"Recommended action: {result.recommended_action}."
        ),
        reasons=[
            JouleFinding(
                code=reason.code,
                severity=reason.severity.value,
                message=reason.message,
            )
            for reason in result.reasons
        ],
        warnings=result.warnings,
        evidence_used=[
            JouleEvidenceUsed(
                file_id=file.file_id,
                filename=file.filename,
                document_type=file.document_type,
                analysis_status=file.analysis_status,
            )
            for file in result.uploaded_files_used
        ],
        component_scores=result.component_scores,
        rule_based_score=result.rule_based_score,
        ml_probability_score=result.ml_probability_score,
        model_version=result.model_version,
    )
