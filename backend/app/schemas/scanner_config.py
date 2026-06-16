"""Scanner-config schemas — tenant-scoped read/update."""
from pydantic import BaseModel, Field


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


class ScannerConfigUpdate(BaseModel):
    ocr_provider: str | None = None
    vision_provider: str | None = None
    fallback_provider: str | None = None
    ollama_base_url: str | None = None
    default_ollama_model: str | None = None
    pdf_ocr_enabled: bool | None = None
    invoice_matching_enabled: bool | None = None
    auto_classification_enabled: bool | None = None
    review_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)