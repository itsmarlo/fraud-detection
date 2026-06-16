from app.models.claim_schema import ClaimInput
from app.services.fraud_scoring_service import FraudScoringService


def test_structured_scoring_is_explainable(claim_payload):
    result = FraudScoringService().score(ClaimInput.model_validate(claim_payload))
    assert 0 <= result.fraud_score <= 100
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
    assert result.reasons
    assert result.warnings
    assert result.ml_probability_score is None


def test_witness_statement_is_not_required_by_policy(claim_payload):
    payload = {
        **claim_payload,
        "third_party_involved": True,
        "has_witness_statement": False,
    }
    result = FraudScoringService().score(ClaimInput.model_validate(payload))

    assert "MISSING_WITNESS_STATEMENT" not in {
        reason.code for reason in result.reasons
    }
