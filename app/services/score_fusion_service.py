from app.core.config import Settings, get_settings


class ScoreFusionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def combine(self, rule_score: float, ml_probability_score: float | None) -> float:
        if ml_probability_score is None:
            return round(rule_score, 2)

        total_weight = self.settings.rule_score_weight + self.settings.ml_score_weight
        combined = (
            self.settings.rule_score_weight * rule_score
            + self.settings.ml_score_weight * ml_probability_score
        ) / total_weight
        return round(min(100.0, max(0.0, combined)), 2)


score_fusion_service = ScoreFusionService()
