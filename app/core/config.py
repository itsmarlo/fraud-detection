from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fraud Detection Claims API"
    app_env: str = "local"
    model_version: str = "fraud-score-v2-calibrated-boosting"
    upload_dir: Path = Path("storage/uploads")
    metadata_file: Path = Path("storage/metadata.json")
    max_upload_size_mb: int = 20
    allowed_image_types: str = "image/jpeg,image/png,image/webp"
    allowed_document_types: str = (
        "application/pdf,text/plain,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    enable_ocr: bool = False
    enable_image_ai: bool = False
    storage_backend: str = "local"
    database_url: str = "sqlite:///storage/metadata.db"
    cors_origins: str = "*"
    approval_threshold_1: float = 5000
    approval_threshold_2: float = 10000
    model_path: Path = Path("app/ml/model.pkl")
    rule_score_weight: float = Field(default=0.6, ge=0)
    ml_score_weight: float = Field(default=0.4, ge=0)
    enable_llm_encoder: bool = False
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-5.5"
    llm_timeout_seconds: float = Field(default=60, gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_score_weights(self) -> "Settings":
        if self.rule_score_weight + self.ml_score_weight <= 0:
            raise ValueError("At least one score weight must be greater than zero")
        return self

    @property
    def image_mime_types(self) -> set[str]:
        return {item.strip() for item in self.allowed_image_types.split(",")}

    @property
    def document_mime_types(self) -> set[str]:
        return {item.strip() for item in self.allowed_document_types.split(",")}

    @property
    def allowed_mime_types(self) -> set[str]:
        return self.image_mime_types | self.document_mime_types

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
