"""Scanner-config schemas — tenant-scoped read/update."""

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings


class ScannerConfigResponse(BaseModel):
    ocr_provider: str
    vision_provider: str
    fallback_provider: str | None
    ollama_base_url: str
    default_ollama_model: str | None
    pdf_ocr_enabled: bool
    invoice_matching_enabled: bool
    auto_classification_enabled: bool
    review_confidence_threshold: float

    # B-42: the Ollama endpoint is deployment configuration, not tenant data. The
    # column still exists, but every reader uses `settings` and the API reports that.
    @field_validator("ollama_base_url", mode="before")
    @classmethod
    def _ollama_url_from_settings(cls, _value):
        return settings.OLLAMA_BASE_URL


class ScannerConfigUpdate(BaseModel):
    """No `ollama_base_url` / `ocr_command` (B-42): deployment settings, not tenant data."""

    ocr_provider: str | None = None
    vision_provider: str | None = None
    fallback_provider: str | None = None
    default_ollama_model: str | None = None
    pdf_ocr_enabled: bool | None = None
    invoice_matching_enabled: bool | None = None
    auto_classification_enabled: bool | None = None
    review_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
