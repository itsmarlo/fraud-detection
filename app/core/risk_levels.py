from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


RECOMMENDED_ACTIONS = {
    RiskLevel.LOW: "Auto-approve",
    RiskLevel.MEDIUM: "Manual claim handler review",
    RiskLevel.HIGH: "Special Investigation Unit review",
    RiskLevel.VERY_HIGH: "Block payment and investigate",
}


def risk_level_for_score(score: float) -> RiskLevel:
    if score <= 30:
        return RiskLevel.LOW
    if score <= 60:
        return RiskLevel.MEDIUM
    if score <= 80:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH
