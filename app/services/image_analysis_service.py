import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

from app.core.config import get_settings
from app.core.risk_levels import RiskLevel
from app.core.rules import reason


class ImageAnalysisService:
    def analyze(
        self,
        image_path: Path,
        accident_date: date | None = None,
        duplicate_claim_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        findings = []
        with Image.open(image_path) as image:
            image.load()
            width, height = image.size
            image_format = image.format or "UNKNOWN"
            exif_timestamp = self._exif_timestamp(image)

        if width < 640 or height < 480:
            findings.append(
                reason(
                    "LOW_RESOLUTION_IMAGE",
                    "Image resolution is too low for reliable damage review.",
                    RiskLevel.MEDIUM,
                    25,
                    "image",
                ).model_dump(mode="json")
            )
        if accident_date and exif_timestamp and exif_timestamp.date() < accident_date:
            findings.append(
                reason(
                    "PHOTO_BEFORE_ACCIDENT",
                    "One damage photo appears to have been captured before the reported accident date.",
                    RiskLevel.VERY_HIGH,
                    70,
                    "image",
                ).model_dump(mode="json")
            )
        if duplicate_claim_ids:
            findings.append(
                reason(
                    "DUPLICATE_IMAGE_ACROSS_CLAIMS",
                    f"Identical image is associated with other claims: {', '.join(duplicate_claim_ids)}.",
                    RiskLevel.VERY_HIGH,
                    80,
                    "image",
                ).model_dump(mode="json")
            )

        return {
            "width": width,
            "height": height,
            "format": image_format,
            "exif_timestamp": exif_timestamp.isoformat() if exif_timestamp else None,
            "checksum": self._checksum(image_path),
            "metadata_extracted": True,
            "findings": findings,
            "damage_severity": self.detect_damage_severity(image_path),
            "description_consistency": {
                "status": "UNKNOWN",
                "reason": "No computer-vision model is configured.",
            },
        }

    @staticmethod
    def _exif_timestamp(image: Image.Image) -> datetime | None:
        exif = image.getexif()
        for tag_id, value in exif.items():
            if ExifTags.TAGS.get(tag_id) in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}:
                try:
                    return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    return None
        return None

    @staticmethod
    def _checksum(image_path: Path) -> str:
        return hashlib.sha256(image_path.read_bytes()).hexdigest()

    @staticmethod
    def detect_damage_severity(image_path: Path) -> dict[str, str]:
        if not get_settings().enable_image_ai:
            return {
                "status": "UNKNOWN",
                "reason": "Image AI is disabled; no damage severity model is configured.",
            }
        return {
            "status": "UNKNOWN",
            "reason": "Image AI is enabled but no computer-vision model is implemented.",
        }

    @staticmethod
    def compare_damage_to_description(
        image_path: Path,
        damage_description: str,
    ) -> dict[str, str]:
        return {
            "status": "UNKNOWN",
            "reason": "No computer-vision comparison model is configured.",
        }


image_analysis_service = ImageAnalysisService()
