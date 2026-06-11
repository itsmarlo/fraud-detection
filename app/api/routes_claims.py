from fastapi import APIRouter

from app.models.claim_schema import BatchClaimInput, ClaimInput
from app.models.scoring_schema import BatchScoringResponse, ScoringResponse
from app.services.fraud_scoring_service import fraud_scoring_service
from app.services.multimodal_fraud_service import multimodal_fraud_service


router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


@router.post("/score", response_model=ScoringResponse)
def score_claim(claim: ClaimInput) -> ScoringResponse:
    return fraud_scoring_service.score(claim)


@router.post("/batch-score", response_model=BatchScoringResponse)
def batch_score_claims(payload: BatchClaimInput) -> BatchScoringResponse:
    return BatchScoringResponse(
        results=[fraud_scoring_service.score(claim) for claim in payload.claims]
    )


@router.post("/{claim_id}/predict-with-files", response_model=ScoringResponse)
def predict_with_files(claim_id: str, claim: ClaimInput) -> ScoringResponse:
    if claim.claim_id != claim_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="Path claim_id must match claim_id in the request body",
        )
    return multimodal_fraud_service.score(claim)
