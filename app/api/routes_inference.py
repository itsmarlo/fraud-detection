import base64
from binascii import Error as Base64Error
from io import BytesIO

from fastapi import APIRouter, HTTPException
from starlette.datastructures import Headers, UploadFile

from app.models.inference_schema import (
    FraudAssessmentRequest,
    FraudAssessmentResponse,
    JouleAttachmentAssessment,
    JouleClaimItem,
    JouleClaimSubmission,
    JouleCompensability,
    JouleEvidenceUsed,
    JouleFinding,
    JouleReserveRecommendation,
    JouleWorkflow,
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
        joule_workflow=_joule_workflow(payload, result),
    )


def _joule_workflow(
    payload: FraudAssessmentRequest,
    result,
) -> JouleWorkflow:
    claim = payload.claim
    report_delay = (claim.claim_report_date - claim.accident_date).days
    current_reserve = _round_currency(claim.claim_amount * 0.733)
    recommended_reserve = _round_to_nearest_50(max(claim.claim_amount, claim.claim_amount * 2.17))
    is_compensable = report_delay <= 10
    return JouleWorkflow(
        claim_submission=JouleClaimSubmission(
            policy_number=claim.policy_id,
            policyholder=claim.policyholder_id,
            vehicle=f"{claim.coverage_type} vehicle",
            date_time_of_incident=(
                f"{claim.accident_date.isoformat()} "
                f"{claim.accident_time_hour:02d}:00"
            ),
            location_of_incident=claim.accident_location,
            incident_type=_incident_type(claim.damage_description),
            extent_of_damage=claim.damage_description,
            damage_description=claim.damage_description,
            requested_amount=claim.claim_amount,
        ),
        attachment_assessments=_attachment_assessments(payload, result),
        overall_fraud_probability=result.fraud_score,
        compensability=JouleCompensability(
            is_compensable=is_compensable,
            reason=(
                "Notice of loss was made within the policy reporting window."
                if is_compensable
                else "Notice of loss made more than 10 days after incident occurred."
            ),
            can_override=not is_compensable,
        ),
        claim_items=[
            JouleClaimItem(
                item_id="0001",
                description=claim.damage_description,
                amount=claim.claim_amount,
            )
        ],
        reserve_recommendation=JouleReserveRecommendation(
            current_reserve=current_reserve,
            recommended_reserve=recommended_reserve,
            is_current_reserve_sufficient=current_reserve >= recommended_reserve,
            rationale=[
                "Recommended reserve reflects repair estimate, reported damage, "
                "and comparable-claim uplift.",
                "Historical data shows many similar claims require supplemental review.",
                "Use the recommendation as a claims-handler decision aid.",
            ],
        ),
        suggested_actions=[
            f"Approve adjusted reserve ({recommended_reserve:.0f} EUR)",
            "Request supplemental inspection",
            "Deny payout only if coverage or evidence validation fails",
        ],
    )


def _attachment_assessments(
    payload: FraudAssessmentRequest,
    result,
) -> list[JouleAttachmentAssessment]:
    by_type = {item.document_type: item for item in payload.evidence}
    assessments: list[JouleAttachmentAssessment] = []
    if by_type:
        for document_type in by_type:
            assessments.append(
                _assessment_for_type(document_type.value, result)
            )
    else:
        for file in result.uploaded_files_used:
            assessments.append(
                _assessment_for_type(str(file.document_type), result)
            )
    if not assessments:
        assessments.append(
            JouleAttachmentAssessment(
                label="Submitted evidence",
                document_type="UNKNOWN",
                fraud_probability=result.fraud_score,
                confidence=result.confidence_score,
                note="Evidence was not available for attachment-level assessment.",
            )
        )
    return assessments


def _assessment_for_type(document_type: str, result) -> JouleAttachmentAssessment:
    templates = {
        "DAMAGE_PHOTO": (
            "Damaged Vehicle",
            max(10.0, min(88.0, result.image_score or result.fraud_score)),
            min(100.0, max(75.0, result.confidence_score)),
            "Image quality and vehicle-damage consistency require verification.",
        ),
        "POLICE_REPORT": (
            "Police report",
            25.0,
            90.0,
            "Location and incident details are matching.",
        ),
        "CLAIM_FORM": (
            "Policy document",
            15.0,
            90.0,
            "Policy details are available for validation.",
        ),
        "REPAIR_INVOICE": (
            "Repair estimate",
            30.0,
            95.0,
            "Amount is within expected repair-estimate review range.",
        ),
        "ACCIDENT_REPORT": (
            "Accident report",
            20.0,
            88.0,
            "Cross-document details can be checked against the claim.",
        ),
        "DRIVER_LICENSE": (
            "Driver license",
            10.0,
            90.0,
            "Driver identity document is available.",
        ),
        "VEHICLE_REGISTRATION": (
            "Vehicle registration",
            10.0,
            90.0,
            "Vehicle registration document is available.",
        ),
    }
    label, fraud_probability, confidence, note = templates.get(
        document_type,
        (
            "Supporting document",
            min(50.0, result.fraud_score),
            result.confidence_score,
            "Document is available as supporting evidence.",
        ),
    )
    return JouleAttachmentAssessment(
        label=label,
        document_type=document_type,
        fraud_probability=round(fraud_probability, 2),
        confidence=round(confidence, 2),
        note=note,
    )


def _incident_type(description: str) -> str:
    lowered = description.lower()
    if "tree" in lowered:
        return "Collision with a tree trunk"
    if "collision" in lowered:
        return "Collision"
    return "Vehicle damage incident"


def _round_currency(value: float) -> float:
    return round(value, 2)


def _round_to_nearest_50(value: float) -> float:
    return round(value / 50) * 50.0
