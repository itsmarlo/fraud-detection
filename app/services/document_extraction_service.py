import hashlib
import re
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

from app.core.config import get_settings


DATE_PATTERN = re.compile(
    r"\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b"
)
AMOUNT_PATTERN = re.compile(
    r"(?<!\w)(?:EUR|USD|€|\$)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2}))"
)
INVOICE_PATTERN = re.compile(
    r"\b(?:invoice|rechnung)(?:\s+(?:number|no\.?|nr\.?))?\s*[:#-]?\s*([A-Z0-9-]{4,})",
    re.IGNORECASE,
)
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b")


class DocumentExtractionService:
    def extract(self, file_path: Path) -> dict[str, Any]:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text = self._pdf_text(file_path)
        elif suffix == ".docx":
            text = self._docx_text(file_path)
        elif suffix == ".txt":
            text = file_path.read_text(encoding="utf-8")
        else:
            raise ValueError(f"Document extraction is not supported for {suffix}")

        dates = DATE_PATTERN.findall(text)
        amounts = [self._parse_amount(value) for value in AMOUNT_PATTERN.findall(text)]
        invoice_match = INVOICE_PATTERN.search(text)
        iban_match = IBAN_PATTERN.search(text.replace(" ", ""))
        return {
            "text_preview": text[:1000],
            "text_length": len(text),
            "extraction_successful": bool(text.strip()),
            "possible_dates": dates[:20],
            "possible_amounts": amounts[:20],
            "possible_invoice_numbers": [invoice_match.group(1)] if invoice_match else [],
            "bank_detail_hash": (
                hashlib.sha256(iban_match.group(0).encode("utf-8")).hexdigest()
                if iban_match
                else None
            ),
            "detected_document_type": self._detect_document_type(text),
            "ocr": self.extract_text_with_ocr(file_path),
        }

    @staticmethod
    def _pdf_text(file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _docx_text(file_path: Path) -> str:
        document = Document(str(file_path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    @staticmethod
    def _parse_amount(value: str) -> float:
        normalized = value.strip()
        if "," in normalized and "." in normalized:
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")
        elif "," in normalized:
            normalized = normalized.replace(",", ".")
        return float(normalized)

    @staticmethod
    def _detect_document_type(text: str) -> str:
        lowered = text.lower()
        keywords = {
            "REPAIR_INVOICE": ("invoice", "rechnung", "repair total"),
            "POLICE_REPORT": (
                "police report",
                "polizeibericht",
                "witness statement",
                "witness",
            ),
            "ACCIDENT_REPORT": ("accident report", "unfallbericht"),
            "CLAIM_FORM": ("claim form", "claimant"),
        }
        for document_type, terms in keywords.items():
            if any(term in lowered for term in terms):
                return document_type
        return "UNKNOWN"

    @staticmethod
    def extract_text_with_ocr(file_path: Path) -> dict[str, str]:
        if not get_settings().enable_ocr:
            return {"status": "DISABLED", "reason": "OCR is disabled by configuration."}
        return {
            "status": "NOT_IMPLEMENTED",
            "reason": (
                "Configure SAP Document Information Extraction, Azure Document "
                "Intelligence, Google Document AI, or Tesseract."
            ),
        }


document_extraction_service = DocumentExtractionService()
