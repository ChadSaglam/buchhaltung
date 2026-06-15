from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.schemas.scanner import ScannerAttempt, ScannerEventStep, ScannerPipelineInfo


@dataclass
class ScannerFile:
    filename: str
    content_type: str
    content: bytes


@dataclass
class ProviderExtractionResult:
    data: dict[str, Any] | None
    steps: list[ScannerEventStep] = field(default_factory=list)
    attempts: list[ScannerAttempt] = field(default_factory=list)
    providers: list[dict[str, str]] = field(default_factory=list)
    selected_model: str | None = None
    ocr_provider: str | None = None
    ocr_worked: bool = False
    error: str | None = None


class BaseScannerProvider(ABC):
    name: str
    provider_type: str
    kind: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError


class BaseOcrProvider(BaseScannerProvider, ABC):
    provider_type = "ocr"

    @abstractmethod
    def extract(self, scanner_file: ScannerFile) -> ProviderExtractionResult:
        raise NotImplementedError


class BaseVisionProvider(BaseScannerProvider, ABC):
    provider_type = "vision"

    @abstractmethod
    def extract(
        self,
        scanner_file: ScannerFile,
        selected_model: str = "",
        preferred_models: list[str] | None = None,
    ) -> ProviderExtractionResult:
        raise NotImplementedError

    @abstractmethod
    def get_status_models(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_vision_model_names(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_best_model(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def get_pipeline(self) -> list[ScannerPipelineInfo]:
        raise NotImplementedError