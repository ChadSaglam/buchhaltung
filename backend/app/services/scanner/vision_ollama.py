from __future__ import annotations

from typing import Any

from app.schemas.scanner import ScannerAttempt, ScannerEventStep, ScannerModelInfo, ScannerPipelineInfo
from app.services.ollama_vision import _is_cloud_model, check_ollama_status, extract_invoice
from app.services.scanner.base import BaseVisionProvider, ProviderExtractionResult, ScannerFile


CUSTOM_OCR_NAME = "custom-ocr"


class OllamaVisionProvider(BaseVisionProvider):
    name = "ollama"
    kind = "local"

    def is_available(self) -> bool:
        status = check_ollama_status()
        return bool(status.get("ok"))

    def get_status_models(self) -> list[dict[str, Any]]:
        status = check_ollama_status()
        if not status.get("ok"):
            return []

        vision_names = set(status.get("vision_models", []))
        models: list[dict[str, Any]] = []
        for model_name in status.get("models", []):
            models.append(
                ScannerModelInfo(
                    name=model_name,
                    provider="vision" if model_name in vision_names else "text",
                    kind="cloud" if _is_cloud_model(model_name) else "local",
                    available=True,
                    working=True,
                    status_label="bereit",
                ).model_dump()
            )
        return models

    def get_vision_model_names(self) -> list[str]:
        status = check_ollama_status()
        if not status.get("ok"):
            return []
        return list(status.get("vision_models", []))

    def get_best_model(self) -> str | None:
        status = check_ollama_status()
        if not status.get("ok"):
            return None
        return status.get("best_vision")

    def get_pipeline(self) -> list[ScannerPipelineInfo]:
        return [
            ScannerPipelineInfo(
                step=1,
                type="ocr",
                name=CUSTOM_OCR_NAME,
                kind="local",
                available=False,
                status_label="optional",
            ),
            ScannerPipelineInfo(
                step=2,
                type="vision-fallback",
                models=self.get_vision_model_names()[:3],
                available=self.is_available(),
                status_label="bereit" if self.is_available() else "nicht erreichbar",
            ),
            ScannerPipelineInfo(step=3, type="classification"),
        ]

    def extract(
        self,
        scanner_file: ScannerFile,
        selected_model: str = "",
        preferred_models: list[str] | None = None,
    ) -> ProviderExtractionResult:
        vision_models = self.get_vision_model_names()
        ranked = self._resolve_ranked_models(selected_model, preferred_models or [], vision_models)
        steps: list[ScannerEventStep] = []
        attempts: list[ScannerAttempt] = []
        providers: list[dict[str, str]] = []

        if not ranked:
            return ProviderExtractionResult(
                data=None,
                steps=steps,
                attempts=attempts,
                providers=providers,
                error="Kein Vision-Modell verfügbar.",
            )

        steps.append(
            ScannerEventStep(
                icon="🔍",
                label=f"{len(ranked)} Vision-Modell(e) werden getestet",
                status="active",
                provider="vision",
            )
        )

        for index, model_name in enumerate(ranked, start=1):
            model_kind = "cloud" if _is_cloud_model(model_name) else "local"
            attempts.append(
                ScannerAttempt(
                    provider="vision",
                    name=model_name,
                    kind=model_kind,
                    status="active",
                    index=index,
                    available=True,
                )
            )
            steps.append(
                ScannerEventStep(
                    icon="🤖",
                    label=f"Versuch {index}: {model_name} ({'Cloud' if model_kind == 'cloud' else 'Lokal'})",
                    status="active",
                    provider="vision",
                    model=model_name,
                )
            )

            data = extract_invoice(scanner_file.content, model_name)
            if data:
                attempts[-1].status = "done"
                providers.append({"type": "vision", "name": model_name, "kind": model_kind})
                steps.append(
                    ScannerEventStep(
                        icon="✅",
                        label=f"Rechnung erkannt mit {model_name}",
                        status="done",
                        provider="vision",
                        model=model_name,
                    )
                )
                return ProviderExtractionResult(
                    data=data,
                    steps=steps,
                    attempts=attempts,
                    providers=providers,
                    selected_model=model_name,
                    ocr_provider="vision-fallback",
                    ocr_worked=False,
                )

            attempts[-1].status = "failed"
            steps.append(
                ScannerEventStep(
                    icon="❌",
                    label=f"{model_name} fehlgeschlagen",
                    status="failed",
                    provider="vision",
                    model=model_name,
                )
            )

        return ProviderExtractionResult(
            data=None,
            steps=steps,
            attempts=attempts,
            providers=providers,
            ocr_provider="vision-fallback",
            ocr_worked=False,
            error="Keine Rechnung erkannt.",
        )

    def _resolve_ranked_models(
        self,
        selected_model: str,
        preferred_models: list[str],
        available_models: list[str],
    ) -> list[str]:
        vision_set = set(available_models)
        selected = (selected_model or "").strip()

        if selected and selected != CUSTOM_OCR_NAME and selected in vision_set:
            return ([selected] + [m for m in available_models if m != selected])[:3]

        preferred = [m for m in preferred_models if m in vision_set and m != CUSTOM_OCR_NAME]
        if preferred:
            return preferred[:3]

        fallback = ["gemma3:12b", "gemma3:4b", "kimi-k2.5:cloud"]
        ranked = [m for m in fallback if m in vision_set]
        if ranked:
            return ranked[:3]

        return [m for m in available_models if m != CUSTOM_OCR_NAME][:3]