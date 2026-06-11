from fastapi import APIRouter, HTTPException

from app.models.scoring_schema import ModelInfoResponse, TrainingResponse
from app.services.model_service import model_service


router = APIRouter(prefix="/api/v1/model", tags=["model"])


@router.post("/train", response_model=TrainingResponse)
def train_model() -> TrainingResponse:
    try:
        return model_service.train()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Model training failed: {exc}") from exc


@router.get("/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    return model_service.info()
