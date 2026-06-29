from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ScannerStatusLiteral = Literal["active", "done", "failed", "pending"]


class ScannerModelInfo(BaseModel):
    name: str
    provider: str | None = None
    kind: str | None = None
    available: bool | None = None
    working: bool | None = None
    status_label: str | None = None


class ScannerPipelineInfo(BaseModel):
    step: int
    type: str
    name: str | None = None
    kind: str | None = None
    models: list[str] = Field(default_factory=list)
    available: bool | None = None
    status_label: str | None = None


class ScannerAttempt(BaseModel):
    provider: str
    name: str
    kind: str
    status: ScannerStatusLiteral
    index: int | None = None
    available: bool | None = None


class ScannerEventStep(BaseModel):
    icon: str
    label: str
    status: ScannerStatusLiteral
    model: str | None = None
    provider: str | None = None
    source: str | None = None
    confidence: float | None = None


class ScannerProviderInfo(BaseModel):
    type: str
    name: str
    kind: str


class ScannerStatusResponse(BaseModel):
    ok: bool
    error: str | None = None
    models: list[ScannerModelInfo] = Field(default_factory=list)
    vision_models: list[str] = Field(default_factory=list)
    best_vision: str | None = None
    scanner_mode: str | None = None
    pipeline: list[ScannerPipelineInfo] = Field(default_factory=list)
    custom_ocr_available: bool = False


class ExtractedLineItem(BaseModel):
    item: str
    amount: float


class ExtractedInvoice(BaseModel):
    vendor: str = ""
    date: str = ""
    invoice_number: str = ""
    total_amount: float = 0.0
    net_amount: float = 0.0
    vat_amount: float = 0.0
    vat_rate: float = 0.0
    description: str = ""
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    kt_soll: str | None = None
    kt_haben: str | None = None
    mwst_code: str | None = None
    mwst_pct: str | None = None
    mwst_amount: float | None = None
    classification_confidence: float | None = None
    classification_source: str | None = None
    classification_input: str | None = None
    vision_model: str | None = None
    ocr_provider: str | None = None
    ocr_worked: bool = False
    custom_ocr_available: bool = False
    scanner_steps: list[ScannerEventStep] = Field(default_factory=list)
    scanner_attempts: list[ScannerAttempt] = Field(default_factory=list)
    scanner_providers: list[ScannerProviderInfo] = Field(default_factory=list)


class ScannerExtractResponse(BaseModel):
    data: ExtractedInvoice


class ScannerConfigResponse(BaseModel):
    tenant_id: int
    ocr_provider: str
    vision_provider: str
    fallback_provider: str | None = None
    ollama_base_url: str
    default_ollama_model: str | None = None
    ocr_command: str | None = None
    pdf_ocr_enabled: bool
    invoice_matching_enabled: bool
    auto_classification_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScannerConfigUpdate(BaseModel):
    ocr_provider: str
    vision_provider: str
    fallback_provider: str | None = None
    ollama_base_url: str
    default_ollama_model: str | None = None
    ocr_command: str | None = None
    pdf_ocr_enabled: bool = True
    invoice_matching_enabled: bool = True
    auto_classification_enabled: bool = True
