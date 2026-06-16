import base64
import json
import os
import ssl
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.models.claim_schema import ClaimInput
from app.models.encoder_schema import ImageSetConsistency, MultimodalEncoding
from app.models.file_schema import DocumentType
from app.services.image_support import ai_image_payload


SYSTEM_PROMPT = """You analyze insurance-claim evidence.
Extract only facts visible in the supplied file. Do not decide whether a person
committed fraud. Identify contradictions, anomalies, or suspicious evidence
that a human investigator should review. Never invent unreadable text, hidden
damage, dates, amounts, identities, or authenticity conclusions. Use UNKNOWN
when the evidence is insufficient."""


class AICoreOrchestrationService:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client or httpx.Client(
            timeout=self.settings.llm_timeout_seconds,
            verify=self._ssl_context(),
        )
        self._cached_token: str | None = None
        self._token_expires_at = 0.0

    def _ssl_context(self) -> ssl.SSLContext:
        configured = self.settings.ssl_cert_file
        environment_bundle = os.getenv("SSL_CERT_FILE") or os.getenv(
            "REQUESTS_CA_BUNDLE"
        )
        certificate_path = configured or (
            Path(environment_bundle) if environment_bundle else None
        )
        if certificate_path:
            if not certificate_path.exists():
                raise ValueError(
                    f"Configured SSL certificate file does not exist: {certificate_path}"
                )
            return ssl.create_default_context(cafile=str(certificate_path))
        return ssl.create_default_context()

    def analyze(
        self,
        file_path: Path,
        content_type: str,
        document_type: DocumentType,
        claim: ClaimInput | None = None,
    ) -> MultimodalEncoding:
        credentials = self._credentials()
        token = self._access_token(credentials)
        response = self.http_client.post(
            self._completion_url(credentials),
            headers={
                "Authorization": f"Bearer {token}",
                "AI-Resource-Group": credentials["resource_group"],
                "Content-Type": "application/json",
            },
            json=self._payload(
                file_path=file_path,
                content_type=content_type,
                document_type=document_type,
                claim=claim,
            ),
        )
        response.raise_for_status()
        content = self._response_content(response.json())
        return MultimodalEncoding.model_validate_json(content)

    def compare_images(
        self,
        images: list[tuple[Path, str]],
        claim: ClaimInput | None,
    ) -> ImageSetConsistency:
        credentials = self._credentials()
        token = self._access_token(credentials)
        response = self.http_client.post(
            self._completion_url(credentials),
            headers={
                "Authorization": f"Bearer {token}",
                "AI-Resource-Group": credentials["resource_group"],
                "Content-Type": "application/json",
            },
            json=self._image_comparison_payload(images, claim),
        )
        response.raise_for_status()
        return ImageSetConsistency.model_validate_json(
            self._response_content(response.json())
        )

    def _access_token(self, credentials: dict[str, str]) -> str:
        if self._cached_token and time.monotonic() < self._token_expires_at:
            return self._cached_token
        response = self.http_client.post(
            credentials["token_url"],
            data={"grant_type": "client_credentials"},
            auth=(credentials["client_id"], credentials["client_secret"]),
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise ValueError("AI Core token response did not contain access_token")
        expires_in = int(response.json().get("expires_in", 300))
        self._cached_token = str(token)
        self._token_expires_at = time.monotonic() + max(0, expires_in - 30)
        return self._cached_token

    def _credentials(self) -> dict[str, str]:
        service_key = self._service_key()
        service_urls = service_key.get("serviceurls", {})
        service_token_url = service_key.get("url", "").rstrip("/")
        if service_token_url:
            service_token_url += "/oauth/token"
        credentials = {
            "base_url": self.settings.aicore_base_url
            or service_urls.get("AI_API_URL", ""),
            "token_url": self.settings.aicore_token_url or service_token_url,
            "client_id": self.settings.aicore_client_id
            or service_key.get("clientid", ""),
            "client_secret": (
                self.settings.aicore_client_secret.get_secret_value()
                if self.settings.aicore_client_secret
                else service_key.get("clientsecret", "")
            ),
            "resource_group": self.settings.aicore_resource_group,
            "deployment_url": self.settings.orch_deployment_url or "",
        }
        required = ("token_url", "client_id", "client_secret")
        missing = [name for name in required if not credentials[name]]
        if missing:
            raise ValueError(
                "Missing SAP AI Core configuration: " + ", ".join(missing)
            )
        if not credentials["deployment_url"] and not credentials["base_url"]:
            raise ValueError(
                "ORCH_DEPLOYMENT_URL or AICORE_BASE_URL must be configured"
            )
        return credentials

    @staticmethod
    def _service_key() -> dict[str, Any]:
        raw = os.getenv("AICORE_SERVICE_KEY", "").strip()
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("AICORE_SERVICE_KEY is not valid JSON") from exc

        vcap_raw = os.getenv("VCAP_SERVICES", "").strip()
        if not vcap_raw:
            return {}
        try:
            services = json.loads(vcap_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("VCAP_SERVICES is not valid JSON") from exc
        for instances in services.values():
            for instance in instances:
                credentials = instance.get("credentials", {})
                service_urls = credentials.get("serviceurls", {})
                if credentials.get("clientid") and service_urls.get("AI_API_URL"):
                    return credentials
        return {}

    def _completion_url(self, credentials: dict[str, str]) -> str:
        deployment_url = credentials["deployment_url"].rstrip("/")
        if deployment_url:
            return (
                deployment_url
                if deployment_url.endswith("/v2/completion")
                else f"{deployment_url}/v2/completion"
            )
        raise ValueError(
            "ORCH_DEPLOYMENT_URL is required when using the raw Python adapter"
        )

    def _payload(
        self,
        file_path: Path,
        content_type: str,
        document_type: DocumentType,
        claim: ClaimInput | None,
    ) -> dict[str, Any]:
        modules: dict[str, Any] = {
            "prompt_templating": {
                "prompt": {
                    "template": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": self._analysis_request(
                                        document_type,
                                        claim,
                                    ),
                                },
                                self._file_content(file_path, content_type),
                            ],
                        },
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "insurance_evidence_encoding",
                            "description": (
                                "Structured semantic analysis of insurance "
                                "claim evidence."
                            ),
                            "schema": MultimodalEncoding.model_json_schema(),
                            "strict": False,
                        },
                    },
                },
                "model": {
                    "name": self.settings.aicore_llm_model,
                    "version": "latest",
                    "params": {"temperature": 0},
                    "timeout": int(self.settings.llm_timeout_seconds),
                },
            }
        }
        if self.settings.masking_required:
            modules["masking"] = {
                "providers": [
                    {
                        "type": "sap_data_privacy_integration",
                        "method": "pseudonymization",
                        "entities": [
                            {"type": "profile-person"},
                            {"type": "profile-email"},
                            {"type": "profile-phone"},
                            {"type": "profile-address"},
                        ],
                        "mask_file_input_method": "anonymization",
                    }
                ]
            }
        return {"config": {"modules": modules}}

    def _image_comparison_payload(
        self,
        images: list[tuple[Path, str]],
        claim: ClaimInput | None,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Compare all supplied claim photos together. Determine whether "
                    "they show the same insured vehicle. Use visible body type, color, "
                    "lights, grille, wheels, badges, registration details, damage "
                    "placement, and stable distinguishing features. Do not mark images "
                    "inconsistent merely because of angle, crop, lighting, or zoom. "
                    "Return UNKNOWN when there is not enough visible evidence. "
                    "Reported damage: "
                    + (claim.damage_description if claim else "Not provided")
                ),
            }
        ]
        content.extend(self._file_content(path, content_type) for path, content_type in images)
        modules: dict[str, Any] = {
            "prompt_templating": {
                "prompt": {
                    "template": [
                        {
                            "role": "system",
                            "content": (
                                "You compare insurance claim photographs. Report only "
                                "visible cross-image vehicle consistency. Do not make a "
                                "fraud determination."
                            ),
                        },
                        {"role": "user", "content": content},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "claim_image_set_consistency",
                            "description": "Cross-image insured vehicle consistency.",
                            "schema": ImageSetConsistency.model_json_schema(),
                            "strict": False,
                        },
                    },
                },
                "model": {
                    "name": self.settings.aicore_llm_model,
                    "version": "latest",
                    "params": {"temperature": 0},
                    "timeout": int(self.settings.llm_timeout_seconds),
                },
            }
        }
        if self.settings.masking_required:
            modules["masking"] = {
                "providers": [
                    {
                        "type": "sap_data_privacy_integration",
                        "method": "pseudonymization",
                        "entities": [
                            {"type": "profile-person"},
                            {"type": "profile-email"},
                            {"type": "profile-phone"},
                            {"type": "profile-address"},
                        ],
                        "mask_file_input_method": "anonymization",
                    }
                ]
            }
        return {"config": {"modules": modules}}

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
    def _file_content(file_path: Path, content_type: str) -> dict[str, Any]:
        if content_type.startswith("image/"):
            image_bytes, image_content_type = ai_image_payload(file_path, content_type)
            encoded = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:{image_content_type};base64,{encoded}"
            return {
                "type": "image_url",
                "image_url": {"url": data_url, "detail": "high"},
            }
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        data_url = f"data:{content_type};base64,{encoded}"
        return {
            "type": "file",
            "file": {"file_data": data_url, "filename": file_path.name},
        }

    @staticmethod
    def _response_content(payload: dict[str, Any]) -> str:
        result = payload.get("orchestration_result") or payload.get("final_result")
        if not result:
            result = payload
        choices = result.get("choices", [])
        if not choices:
            raise ValueError("AI Core response did not contain choices")
        content = choices[0].get("message", {}).get("content")
        if not content:
            raise ValueError("AI Core response did not contain message content")
        return str(content)
