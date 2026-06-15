from __future__ import annotations

from app.services.scanner.base import BaseOcrProvider, BaseVisionProvider
from app.services.scanner.ocr_tesseract import TesseractOcrProvider
from app.services.scanner.vision_ollama import OllamaVisionProvider


class ScannerProviderRegistry:
    def __init__(self) -> None:
        self._ocr_providers: dict[str, BaseOcrProvider] = {
            "custom-ocr": TesseractOcrProvider(),
            "tesseract": TesseractOcrProvider(),
        }
        self._vision_providers: dict[str, BaseVisionProvider] = {
            "ollama": OllamaVisionProvider(),
        }

    def get_ocr_provider(self, name: str = "custom-ocr") -> BaseOcrProvider:
        return self._ocr_providers.get(name, self._ocr_providers["custom-ocr"])

    def get_vision_provider(self, name: str = "ollama") -> BaseVisionProvider:
        return self._vision_providers[name]

    def custom_ocr_available(self) -> bool:
        return self.get_ocr_provider("custom-ocr").is_available()

    def list_status_models(self) -> list[dict]:
        ocr = self.get_ocr_provider("custom-ocr")
        available = ocr.is_available()
        return [
            {
                "name": "custom-ocr",
                "provider": "ocr",
                "kind": "local",
                "available": available,
                "working": available,
                "status_label": "bereit" if available else "Tesseract nicht installiert",
            },
            *self.get_vision_provider("ollama").get_status_models(),
        ]