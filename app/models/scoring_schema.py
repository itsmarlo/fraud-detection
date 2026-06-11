from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.risk_levels import RiskLevel


class RiskReason(BaseModel):
    code: str
    message: str
    severity: RiskLevel
    points: float = Field(default=0, exclude=True)
    component: str | None = Field(default=None, exclude=True)


class UploadedFileUsed(BaseModel):
    file_id: str
    document_type: str
    filename: str
    analysis_status: str


class ExtractionSummary(BaseModel):
    documents_processed: int = 0
    images_processed: int = 0
    text_extraction_successful: int = 0
    image_metadata_extracted: int = 0
    llm_files_encoded: int = 0


class ScoringResponse(BaseModel):
    claim_id: str
    fraud_score: float
    risk_level: RiskLevel
    recommended_action: str
    confidence_score: float
    structured_claim_score: float
    document_score: float
    image_score: float
    network_score: float
    rule_based_score: float
    ml_probability_score: float | None = None
    uploaded_files_used: list[UploadedFileUsed] = Field(default_factory=list)
    component_scores: dict[str, float]
    reasons: list[RiskReason]
    warnings: list[str] = Field(default_factory=list)
    extraction_summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    model_version: str
    timestamp: datetime


class BatchScoringResponse(BaseModel):
    results: list[ScoringResponse]


class TrainingResponse(BaseModel):
    model_version: str
    model_type: str
    training_samples: int
    fraud_rate: float
    accuracy: float
    roc_auc: float | None
    brier_score: float
    feature_list: list[str]
    trained_at: datetime


class ModelInfoResponse(BaseModel):
    model_version: str
    model_type: str
    trained_at: datetime | None
    feature_list: list[str]
    available: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
