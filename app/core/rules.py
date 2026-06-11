from app.core.risk_levels import RiskLevel
from app.models.scoring_schema import RiskReason


def reason(
    code: str,
    message: str,
    severity: RiskLevel,
    points: float,
    component: str,
) -> RiskReason:
    return RiskReason(
        code=code,
        message=message,
        severity=severity,
        points=points,
        component=component,
    )
