from app.core.risk_levels import RiskLevel
from app.core.rules import reason
from app.models.claim_schema import ClaimInput
from app.models.file_schema import FileMetadata
from app.models.scoring_schema import RiskReason
from app.services.file_metadata_service import FileMetadataService, file_metadata_service


class NetworkRiskService:
    def __init__(self, metadata_service: FileMetadataService | None = None) -> None:
        self.metadata_service = metadata_service or file_metadata_service

    def score(
        self,
        claim: ClaimInput,
        files: list[FileMetadata],
    ) -> tuple[float, list[RiskReason]]:
        score = 0.0
        findings: list[RiskReason] = []
        identity_rules = [
            (
                "bank_account_hash",
                claim.bank_account_hash,
                "BANK_ACCOUNT_REUSED",
                "Bank account hash is shared with other claims",
                35,
            ),
            (
                "phone_hash",
                claim.phone_hash,
                "PHONE_REUSED",
                "Phone hash is shared with other claims",
                25,
            ),
            (
                "email_hash",
                claim.email_hash,
                "EMAIL_REUSED",
                "Email hash is shared with other claims",
                20,
            ),
        ]
        for field, value, code, message, points in identity_rules:
            related = self.metadata_service.claims_for_identity(
                field,
                value,
                claim.claim_id,
            )
            if related:
                score += points
                findings.append(
                    reason(
                        code,
                        f"{message}: {', '.join(related)}.",
                        RiskLevel.HIGH,
                        points,
                        "network",
                    )
                )
        duplicate_claims: set[str] = set()
        for file in files:
            duplicate_claims.update(
                self.metadata_service.claims_for_checksum(file.checksum, claim.claim_id)
            )
        if duplicate_claims:
            score += 55
            findings.append(
                reason(
                    "FILES_REUSED_ACROSS_CLAIMS",
                    f"Uploaded content is also used by claims: {', '.join(sorted(duplicate_claims))}.",
                    RiskLevel.VERY_HIGH,
                    55,
                    "network",
                )
            )
        if claim.garage_previous_suspicious_claims >= 5:
            score += 30
            findings.append(
                reason(
                    "GARAGE_NETWORK_RISK",
                    "Garage is connected to many suspicious claims.",
                    RiskLevel.HIGH,
                    30,
                    "network",
                )
            )
        self.metadata_service.register_claim_identity(
            claim.claim_id,
            claim.bank_account_hash,
            claim.phone_hash,
            claim.email_hash,
        )
        return min(100.0, score), findings


network_risk_service = NetworkRiskService()
