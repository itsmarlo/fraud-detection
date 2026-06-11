from typing import Literal

from pydantic import BaseModel, Field


class MultimodalEncoding(BaseModel):
    summary: str
    detected_document_type: str = "UNKNOWN"
    confidence_score: float = Field(ge=0, le=100)
    evidence_risk_score: float = Field(ge=0, le=100)
    extracted_dates: list[str] = Field(default_factory=list)
    extracted_amounts: list[float] = Field(default_factory=list)
    document_numbers: list[str] = Field(default_factory=list)
    visual_observations: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    suspicious_indicators: list[str] = Field(default_factory=list)
    damage_severity: Literal["UNKNOWN", "MINOR", "MODERATE", "SEVERE"] = "UNKNOWN"
    description_consistency: Literal[
        "UNKNOWN",
        "CONSISTENT",
        "PARTIALLY_CONSISTENT",
        "INCONSISTENT",
    ] = "UNKNOWN"
