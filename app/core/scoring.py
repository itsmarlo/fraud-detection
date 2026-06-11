from datetime import timedelta

from app.core.config import get_settings
from app.core.risk_levels import RiskLevel
from app.core.rules import reason
from app.models.claim_schema import ClaimInput
from app.models.scoring_schema import RiskReason


STRUCTURED_WEIGHTS = {
    "policyholder_history": 0.20,
    "claim_behavior": 0.20,
    "damage_repair_consistency": 0.25,
    "document_validation": 0.20,
    "network_risk": 0.15,
}


def _bounded(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 2)


def score_structured_claim(claim: ClaimInput) -> tuple[dict[str, float], list[RiskReason]]:
    findings: list[RiskReason] = []
    settings = get_settings()

    days_since_start = (claim.accident_date - claim.policy_start_date).days
    policy_score = 0.0
    if 0 <= days_since_start <= 30:
        policy_score += 30
        findings.append(reason("NEW_POLICY_CLAIM", "Claim occurred within 30 days of policy start.", RiskLevel.HIGH, 30, "policyholder_history"))
    if claim.number_of_previous_claims >= 3:
        points = min(30, claim.number_of_previous_claims * 6)
        policy_score += points
        findings.append(reason("MULTIPLE_PREVIOUS_CLAIMS", "Policyholder has multiple previous claims.", RiskLevel.MEDIUM, points, "policyholder_history"))
    if claim.number_of_previous_rejected_claims:
        points = min(30, claim.number_of_previous_rejected_claims * 15)
        policy_score += points
        findings.append(reason("PREVIOUS_REJECTED_CLAIMS", "Policyholder has previously rejected claims.", RiskLevel.HIGH, points, "policyholder_history"))
    if claim.recent_policy_change:
        policy_score += 15
        findings.append(reason("RECENT_POLICY_CHANGE", "Policy was changed shortly before the claim.", RiskLevel.MEDIUM, 15, "policyholder_history"))
    if claim.premium_payment_status.upper() not in {"PAID", "CURRENT"}:
        policy_score += 25
        findings.append(reason("PREMIUM_NOT_CURRENT", "Premium payment is not current.", RiskLevel.HIGH, 25, "policyholder_history"))

    behavior_score = 0.0
    report_delay = (claim.claim_report_date - claim.accident_date).days
    if report_delay > 7:
        points = 15 if report_delay <= 30 else 30
        behavior_score += points
        findings.append(reason("DELAYED_REPORTING", f"Claim was reported {report_delay} days after the accident.", RiskLevel.MEDIUM, points, "claim_behavior"))
    if claim.claim_amount / claim.vehicle_value > 0.7:
        behavior_score += 35
        findings.append(reason("CLAIM_VALUE_RATIO_HIGH", "Claim amount is unusually high compared with vehicle value.", RiskLevel.HIGH, 35, "claim_behavior"))
    if any(abs(claim.claim_amount - threshold) <= max(50, threshold * 0.01) for threshold in (settings.approval_threshold_1, settings.approval_threshold_2)):
        behavior_score += 20
        findings.append(reason("CLAIM_NEAR_APPROVAL_THRESHOLD", "Claim amount is close to an approval threshold.", RiskLevel.MEDIUM, 20, "claim_behavior"))
    if 0 <= claim.accident_time_hour <= 5:
        behavior_score += 15
        findings.append(reason("UNUSUAL_ACCIDENT_TIME", "Accident occurred between midnight and 05:00.", RiskLevel.MEDIUM, 15, "claim_behavior"))
    if not claim.accident_location or len(claim.damage_description.strip()) < 10:
        behavior_score += 20
        findings.append(reason("INCOMPLETE_CLAIM_DETAILS", "Important accident or damage information is incomplete.", RiskLevel.MEDIUM, 20, "claim_behavior"))

    damage_score = 0.0
    if claim.repair_estimate_amount / claim.vehicle_value > 0.65:
        damage_score += 35
        findings.append(reason("REPAIR_ESTIMATE_TOO_HIGH", "Repair estimate is high compared with vehicle value.", RiskLevel.HIGH, 35, "damage_repair_consistency"))
    if claim.garage_previous_suspicious_claims >= 3:
        points = min(35, claim.garage_previous_suspicious_claims * 5)
        damage_score += points
        findings.append(reason("SUSPICIOUS_GARAGE_HISTORY", "Garage is linked to several suspicious claims.", RiskLevel.HIGH, points, "damage_repair_consistency"))
    if not claim.has_damage_photos:
        damage_score += 20
        findings.append(reason("NO_DAMAGE_PHOTOS", "No damage photos were declared.", RiskLevel.MEDIUM, 20, "damage_repair_consistency"))
    if not claim.has_repair_invoice:
        damage_score += 15
        findings.append(reason("NO_REPAIR_INVOICE", "No repair invoice was declared.", RiskLevel.MEDIUM, 15, "damage_repair_consistency"))
    if len(claim.damage_description.strip()) < 20:
        damage_score += 15
        findings.append(reason("VAGUE_DAMAGE_DESCRIPTION", "Damage description is too short or vague.", RiskLevel.MEDIUM, 15, "damage_repair_consistency"))

    document_score = 0.0
    if claim.claim_amount >= settings.approval_threshold_1 and not claim.has_police_report:
        document_score += 30
        findings.append(reason("MISSING_POLICE_REPORT", "Police report is missing for a high-value claim.", RiskLevel.MEDIUM, 30, "document_validation"))
    if claim.invoice_date and claim.invoice_date < claim.accident_date:
        document_score += 45
        findings.append(reason("INVOICE_BEFORE_ACCIDENT", "Invoice date is before the reported accident date.", RiskLevel.VERY_HIGH, 45, "document_validation"))
    if claim.photo_capture_date and claim.photo_capture_date < claim.accident_date:
        document_score += 50
        findings.append(reason("PHOTO_BEFORE_ACCIDENT", "Damage photo date is before the reported accident date.", RiskLevel.VERY_HIGH, 50, "document_validation"))
    if claim.invoice_date and claim.invoice_date > claim.claim_report_date + timedelta(days=365):
        document_score += 20
        findings.append(reason("INVOICE_DATE_IMPLAUSIBLE", "Invoice date is implausibly late for this claim.", RiskLevel.MEDIUM, 20, "document_validation"))

    network_score = 0.0
    if claim.garage_previous_suspicious_claims >= 5:
        network_score += 45
        findings.append(reason("GARAGE_NETWORK_RISK", "Garage has a high-risk claim network.", RiskLevel.HIGH, 45, "network_risk"))
    if claim.third_party_involved and not claim.has_witness_statement:
        network_score += 30
        findings.append(reason("MISSING_WITNESS_STATEMENT", "Third party is involved but no witness statement is available.", RiskLevel.HIGH, 30, "network_risk"))

    components = {
        "policyholder_history": _bounded(policy_score),
        "claim_behavior": _bounded(behavior_score),
        "damage_repair_consistency": _bounded(damage_score),
        "document_validation": _bounded(document_score),
        "network_risk": _bounded(network_score),
    }
    return components, findings


def structured_total(components: dict[str, float]) -> float:
    return round(sum(components[key] * weight for key, weight in STRUCTURED_WEIGHTS.items()), 2)
