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


class JouleClaimSubmission(BaseModel):
    policy_number: str
    policyholder: str
    vehicle: str
    date_time_of_incident: str
    location_of_incident: str
    incident_type: str
    extent_of_damage: str
    damage_description: str
    requested_amount: float
    currency: str = "EUR"


class JouleAttachmentAssessment(BaseModel):
    label: str
    document_type: str
    fraud_probability: float
    confidence: float
    note: str


class JouleCompensability(BaseModel):
    is_compensable: bool
    reason: str
    can_override: bool


class JouleClaimItem(BaseModel):
    item_id: str
    description: str
    amount: float
    currency: str = "EUR"


class JouleReserveRecommendation(BaseModel):
    current_reserve: float
    recommended_reserve: float
    currency: str = "EUR"
    is_current_reserve_sufficient: bool
    rationale: list[str]


class JouleWorkflow(BaseModel):
    claim_submission: JouleClaimSubmission
    attachment_assessments: list[JouleAttachmentAssessment]
    overall_fraud_probability: float
    compensability: JouleCompensability
    claim_items: list[JouleClaimItem]
    reserve_recommendation: JouleReserveRecommendation
    suggested_actions: list[str]


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
    joule_workflow: JouleWorkflow
