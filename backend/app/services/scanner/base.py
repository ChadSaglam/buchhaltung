from __future__ import annotations

import asyncio
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

    # Async members are what the request path uses (B-49); the sync ones stay for
    # scripts and tests. Defaults run the sync member in a worker thread.
    async def is_available_async(self) -> bool:
        return await asyncio.to_thread(self.is_available)

    async def extract_async(
        self,
        scanner_file: ScannerFile,
        selected_model: str = "",
        preferred_models: list[str] | None = None,
    ) -> ProviderExtractionResult:
        return await asyncio.to_thread(self.extract, scanner_file, selected_model, preferred_models)

    async def get_status_models_async(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.get_status_models)

    async def get_vision_model_names_async(self) -> list[str]:
        return await asyncio.to_thread(self.get_vision_model_names)

    async def get_best_model_async(self) -> str | None:
        return await asyncio.to_thread(self.get_best_model)

    async def get_pipeline_async(self) -> list[ScannerPipelineInfo]:
        return await asyncio.to_thread(self.get_pipeline)

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
