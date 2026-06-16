import base64
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.risk_levels import RiskLevel
from app.core.rules import reason
from app.models.claim_schema import ClaimInput
from app.models.encoder_schema import ImageSetConsistency, MultimodalEncoding
from app.models.file_schema import DocumentType
from app.services.aicore_orchestration_service import AICoreOrchestrationService
from app.services.image_support import ai_image_payload


SYSTEM_PROMPT = """You analyze insurance-claim evidence.
Extract only facts visible in the supplied file. Do not decide whether a person
committed fraud. Identify contradictions, anomalies, or suspicious evidence
that a human investigator should review. Never invent unreadable text, hidden
damage, dates, amounts, identities, or authenticity conclusions. Use UNKNOWN
when the evidence is insufficient. Return the requested structured output."""


class MultimodalEncoderService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        aicore_service: AICoreOrchestrationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self.aicore_service = aicore_service

    def _get_aicore_service(self) -> AICoreOrchestrationService:
        if self.aicore_service is None:
            self.aicore_service = AICoreOrchestrationService(settings=self.settings)
        return self.aicore_service

    def analyze(
        self,
        file_path: Path,
        content_type: str,
        document_type: DocumentType,
        claim: ClaimInput | None = None,
    ) -> dict[str, Any]:
        if not self.settings.enable_llm_encoder:
            return {
                "status": "DISABLED",
                "reason": "Multimodal LLM encoding is disabled by configuration.",
            }
        if self.settings.llm_provider == "btp":
            return self._analyze_with_btp(
                file_path,
                content_type,
                document_type,
                claim,
            )
        if not self.settings.openai_api_key and self._client is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "OPENAI_API_KEY is not configured.",
            }
        return self._analyze_with_openai(
            file_path,
            content_type,
            document_type,
            claim,
        )

    def compare_images(
        self,
        images: list[tuple[Path, str]],
        claim: ClaimInput,
    ) -> dict[str, Any]:
        if len(images) < 2:
            return {
                "status": "NOT_APPLICABLE",
                "reason": "At least two images are required for comparison.",
                "findings": [],
            }
        if not self.settings.enable_llm_encoder:
            return {
                "status": "DISABLED",
                "reason": "Cross-image AI comparison is disabled by configuration.",
                "findings": [],
            }
        try:
            if self.settings.llm_provider == "btp":
                result = self._get_aicore_service().compare_images(images, claim)
                provider = "sap_ai_core"
                model = self.settings.aicore_llm_model
            else:
                if not self.settings.openai_api_key and self._client is None:
                    raise ValueError("OPENAI_API_KEY is not configured.")
                content = [
                    {
                        "type": "input_text",
                        "text": (
                            "Compare all supplied claim photos together and determine "
                            "whether they show the same insured vehicle. Consider body "
                            "type, color, lights, grille, wheels, badges, registration "
                            "details, damage placement, and stable distinguishing "
                            "features. Ignore differences caused only by angle, crop, "
                            "lighting, or zoom. Return UNKNOWN when evidence is limited. "
                            f"Reported damage: {claim.damage_description}"
                        ),
                    },
                    *[
                        self._file_content(path, content_type)
                        for path, content_type in images
                    ],
                ]
                response = self._get_client().responses.parse(
                    model=self.settings.llm_model,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "Compare insurance claim photographs for same-vehicle "
                                "consistency. Report visible facts only and do not make "
                                "a fraud determination."
                            ),
                        },
                        {"role": "user", "content": content},
                    ],
                    text_format=ImageSetConsistency,
                )
                result = response.output_parsed
                if result is None:
                    raise ValueError("The model did not return structured output")
                provider = "openai"
                model = self.settings.llm_model
            payload = result.model_dump(mode="json")
            payload.update(
                {
                    "status": "COMPLETED",
                    "provider": provider,
                    "model": model,
                    "findings": self._image_set_findings(result),
                }
            )
            return payload
        except Exception as exc:
            return {
                "status": "FAILED",
                "reason": str(exc),
                "findings": [],
            }

    def _analyze_with_btp(
        self,
        file_path: Path,
        content_type: str,
        document_type: DocumentType,
        claim: ClaimInput | None,
    ) -> dict[str, Any]:
        try:
            encoding = self._get_aicore_service().analyze(
                file_path=file_path,
                content_type=content_type,
                document_type=document_type,
                claim=claim,
            )
            result = encoding.model_dump(mode="json")
            result.update(
                {
                    "status": "COMPLETED",
                    "provider": "sap_ai_core",
                    "model": self.settings.aicore_llm_model,
                    "findings": self._findings(encoding),
                }
            )
            return result
        except Exception as exc:
            return {
                "status": "FAILED",
                "provider": "sap_ai_core",
                "model": self.settings.aicore_llm_model,
                "reason": str(exc),
                "findings": [],
            }

    def _analyze_with_openai(
        self,
        file_path: Path,
        content_type: str,
        document_type: DocumentType,
        claim: ClaimInput | None,
    ) -> dict[str, Any]:
        try:
            response = self._get_client().responses.parse(
                model=self.settings.llm_model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": self._analysis_request(document_type, claim),
                            },
                            self._file_content(file_path, content_type),
                        ],
                    },
                ],
                text_format=MultimodalEncoding,
            )
            encoding = response.output_parsed
            if encoding is None:
                raise ValueError("The model did not return structured output")
            result = encoding.model_dump(mode="json")
            result.update(
                {
                    "status": "COMPLETED",
                    "provider": "openai",
                    "model": self.settings.llm_model,
                    "findings": self._findings(encoding),
                }
            )
            return result
        except Exception as exc:
            return {
                "status": "FAILED",
                "provider": "openai",
                "model": self.settings.llm_model,
                "reason": str(exc),
                "findings": [],
            }

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.openai_api_key.get_secret_value(),
                timeout=self.settings.llm_timeout_seconds,
            )
        return self._client

    @staticmethod
    def _analysis_request(
        document_type: DocumentType,
        claim: ClaimInput | None,
    ) -> str:
        lines = [
            f"Analyze this file as declared evidence type {document_type.value}.",
            "Extract relevant dates, amounts, reference numbers, visible damage, "
            "and evidence inconsistencies.",
        ]
        if claim:
            lines.extend(
                [
                    f"Reported accident date: {claim.accident_date.isoformat()}",
                    f"Claim amount: {claim.claim_amount}",
                    f"Repair estimate: {claim.repair_estimate_amount}",
                    f"Reported damage: {claim.damage_description}",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _file_content(file_path: Path, content_type: str) -> dict[str, str]:
        if content_type.startswith("image/"):
            image_bytes, image_content_type = ai_image_payload(file_path, content_type)
            encoded = base64.b64encode(image_bytes).decode("ascii")
            return {
                "type": "input_image",
                "image_url": f"data:{image_content_type};base64,{encoded}",
                "detail": "high",
            }
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        return {
            "type": "input_file",
            "filename": file_path.name,
            "file_data": f"data:{content_type};base64,{encoded}",
        }

    @staticmethod
    def _findings(encoding: MultimodalEncoding) -> list[dict[str, Any]]:
        if (
            encoding.evidence_risk_score < 60
            or not (encoding.inconsistencies or encoding.suspicious_indicators)
        ):
            return []

        details = (encoding.inconsistencies + encoding.suspicious_indicators)[:3]
        severity = (
            RiskLevel.HIGH
            if encoding.evidence_risk_score < 80
            else RiskLevel.VERY_HIGH
        )
        return [
            reason(
                "LLM_EVIDENCE_INCONSISTENCY",
                "Multimodal evidence review identified: " + "; ".join(details),
                severity,
                min(80, encoding.evidence_risk_score),
                "multimodal_encoder",
            ).model_dump(mode="json")
        ]

    @staticmethod
    def _image_set_findings(
        comparison: ImageSetConsistency,
    ) -> list[dict[str, Any]]:
        if (
            comparison.vehicle_consistency != "INCONSISTENT"
            or comparison.confidence_score < 70
        ):
            return []
        return [
            reason(
                "DIFFERENT_VEHICLES_ACROSS_PHOTOS",
                comparison.explanation,
                RiskLevel.VERY_HIGH,
                80,
                "image",
            ).model_dump(mode="json")
        ]


multimodal_encoder_service = MultimodalEncoderService()
