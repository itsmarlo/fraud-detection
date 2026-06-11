from app.core.config import Settings
from app.services.score_fusion_service import ScoreFusionService


def test_score_fusion_returns_rule_score_without_model():
    service = ScoreFusionService(Settings(rule_score_weight=0.6, ml_score_weight=0.4))

    assert service.combine(72.345, None) == 72.34


def test_score_fusion_normalizes_configured_weights():
    service = ScoreFusionService(Settings(rule_score_weight=3, ml_score_weight=2))

    assert service.combine(80, 30) == 60


def test_score_fusion_clamps_result_to_probability_range():
    service = ScoreFusionService(Settings(rule_score_weight=0, ml_score_weight=1))

    assert service.combine(50, 120) == 100
