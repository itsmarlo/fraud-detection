from pydantic import BaseModel, Field

from app.models.claim_schema import ClaimInput
from app.models.file_schema import DocumentType


class InlineEvidence(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    document_type: DocumentType
    content_base64: str = Field(min_length=1)


class FraudAssessmentRequest(BaseModel):
    claim: ClaimInput
    evidence: list[InlineEvidence] = Field(default_factory=list)
    replace_existing_evidence: bool = True


class JouleFinding(BaseModel):
    code: str
    severity: str
    message: str


class JouleEvidenceUsed(BaseModel):
    file_id: str
    filename: str
    document_type: str
    analysis_status: str


class FraudAssessmentResponse(BaseModel):
    claim_id: str
    fraud_score: float
    risk_level: str
    confidence_score: float
    recommended_action: str
    summary: str
    reasons: list[JouleFinding]
    warnings: list[str]
    evidence_used: list[JouleEvidenceUsed]
    component_scores: dict[str, float]
    rule_based_score: float
    ml_probability_score: float | None = None
    model_version: str
