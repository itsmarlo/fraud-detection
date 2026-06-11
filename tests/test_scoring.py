from app.models.claim_schema import ClaimInput
from app.services.fraud_scoring_service import FraudScoringService


def test_structured_scoring_is_explainable(claim_payload):
    result = FraudScoringService().score(ClaimInput.model_validate(claim_payload))
    assert 0 <= result.fraud_score <= 100
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
    assert result.reasons
    assert result.warnings
    assert result.ml_probability_score is None
