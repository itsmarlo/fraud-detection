from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.risk_levels import RECOMMENDED_ACTIONS, risk_level_for_score
from app.core.scoring import score_structured_claim, structured_total
from app.models.claim_schema import ClaimInput
from app.models.scoring_schema import ExtractionSummary, ScoringResponse
from app.services.model_service import ModelService, model_service
from app.services.network_risk_service import NetworkRiskService, network_risk_service
from app.services.score_fusion_service import ScoreFusionService, score_fusion_service


class FraudScoringService:
    def __init__(
        self,
        ml_service: ModelService | None = None,
        network_service: NetworkRiskService | None = None,
        fusion_service: ScoreFusionService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.ml_service = ml_service or model_service
        self.network_service = network_service or network_risk_service
        self.fusion_service = fusion_service or score_fusion_service

    def score(self, claim: ClaimInput) -> ScoringResponse:
        components, findings = score_structured_claim(claim)
        network_score, network_findings = self.network_service.score(claim, [])
        components["network_risk"] = max(components["network_risk"], network_score)
        findings = [
            item for item in findings if item.component != "network_risk"
        ] + network_findings
        rule_score = structured_total(components)
        ml_score = self.ml_service.predict(claim)
        final_score = self.fusion_service.combine(rule_score, ml_score)
        risk_level = risk_level_for_score(final_score)
        confidence = self._structured_confidence(claim)
        return ScoringResponse(
            claim_id=claim.claim_id,
            fraud_score=final_score,
            risk_level=risk_level,
            recommended_action=RECOMMENDED_ACTIONS[risk_level],
            confidence_score=confidence,
            structured_claim_score=rule_score,
            document_score=components["document_validation"],
            image_score=0,
            network_score=components["network_risk"],
            rule_based_score=rule_score,
            ml_probability_score=ml_score,
            component_scores={
                "structured_claim_score": rule_score,
                "document_score": components["document_validation"],
                "image_score": 0.0,
                "network_score": components["network_risk"],
            },
            reasons=findings,
            warnings=[
                "No documents or images were uploaded. Fraud score confidence is reduced."
            ],
            extraction_summary=ExtractionSummary(),
            model_version=self.settings.model_version,
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def _structured_confidence(claim: ClaimInput) -> float:
        score = 45.0
        score += 8 if claim.has_damage_photos else 0
        score += 8 if claim.has_repair_invoice else 0
        score += 7 if claim.has_police_report or claim.claim_amount < 5000 else 0
        score += 5 if len(claim.damage_description.strip()) >= 20 else 0
        score += 5 if claim.accident_location.strip() else 0
        return min(70.0, round(score, 2))


fraud_scoring_service = FraudScoringService()
