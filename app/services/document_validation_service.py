from app.core.risk_levels import RiskLevel
from app.core.rules import reason
from app.models.document_schema import (
    DocumentValidationResponse,
    ExtractedDocumentMetadata,
)


class DocumentValidationService:
    def validate(
        self,
        metadata: ExtractedDocumentMetadata,
    ) -> DocumentValidationResponse:
        available = set(metadata.available_document_types)
        required = {"CLAIM_FORM", "DAMAGE_PHOTO", "REPAIR_INVOICE", "DRIVER_LICENSE", "VEHICLE_REGISTRATION"}
        if metadata.claim_amount >= metadata.high_value_threshold:
            required.add("POLICE_REPORT")
        missing = sorted(required - available)
        findings = []
        score = 0.0

        for document_type in missing:
            severity = RiskLevel.MEDIUM
            points = 10
            if document_type == "POLICE_REPORT":
                code = "MISSING_POLICE_REPORT"
                message = "Police report is missing for a high-value claim."
                points = 20
            else:
                code = f"MISSING_{document_type}"
                message = f"Mandatory document {document_type} is missing."
            findings.append(reason(code, message, severity, points, "document").model_dump(mode="json"))
            score += points

        if metadata.invoice_date and metadata.invoice_date < metadata.accident_date:
            findings.append(reason("INVOICE_BEFORE_ACCIDENT", "Invoice date is before the accident date.", RiskLevel.VERY_HIGH, 45, "document").model_dump(mode="json"))
            score += 45
        if metadata.photo_date and metadata.photo_date < metadata.accident_date:
            findings.append(reason("PHOTO_BEFORE_ACCIDENT", "Photo date is before the accident date.", RiskLevel.VERY_HIGH, 50, "document").model_dump(mode="json"))
            score += 50
        if metadata.police_report_date and abs((metadata.police_report_date - metadata.accident_date).days) > 7:
            findings.append(reason("POLICE_REPORT_DATE_INCONSISTENT", "Police report date differs from the accident date by more than seven days.", RiskLevel.HIGH, 30, "document").model_dump(mode="json"))
            score += 30
        if metadata.repair_invoice_amount and metadata.repair_invoice_amount > metadata.claim_amount:
            findings.append(reason("INVOICE_EXCEEDS_CLAIM", "Repair invoice amount is higher than the claim amount.", RiskLevel.HIGH, 35, "document").model_dump(mode="json"))
            score += 35
        if metadata.repair_invoice_amount and metadata.repair_invoice_amount / metadata.vehicle_value > 0.7:
            findings.append(reason("INVOICE_AMOUNT_TOO_HIGH", "Repair invoice amount is unusually high compared to the vehicle value.", RiskLevel.HIGH, 35, "document").model_dump(mode="json"))
            score += 35
        if metadata.duplicate_checksums:
            findings.append(reason("DUPLICATE_DOCUMENT_CHECKSUM", "Duplicate documents were detected.", RiskLevel.HIGH, 35, "document").model_dump(mode="json"))
            score += 35
        if metadata.invoice_used_by_claim_ids:
            findings.append(reason("INVOICE_REUSED_ACROSS_CLAIMS", "The same invoice appears in unrelated claims.", RiskLevel.VERY_HIGH, 60, "document").model_dump(mode="json"))
            score += 60
        if metadata.bank_detail_used_by_claim_ids:
            findings.append(reason("BANK_DETAILS_REUSED", "The same bank details appear in unrelated claims.", RiskLevel.HIGH, 45, "document").model_dump(mode="json"))
            score += 45

        return DocumentValidationResponse(
            document_score=round(min(100.0, score), 2),
            findings=findings,
            missing_documents=missing,
        )


document_validation_service = DocumentValidationService()
