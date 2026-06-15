from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

from app.schemas.scanner import ScannerAttempt, ScannerEventStep, ScannerModelInfo, ScannerPipelineInfo
from app.services.ollama_vision import (
    _is_cloud_model,
    check_ollama_status_async,
    extract_invoice_async,
)
from app.services.scanner.base import BaseVisionProvider, ProviderExtractionResult, ScannerFile

CUSTOM_OCR_NAME = "custom-ocr"

def _run_sync(coro):
    """Run a coroutine safely from sync code, even if a loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)

class OllamaVisionProvider(BaseVisionProvider):
    name = "ollama"
    kind = "local"

    async def is_available_async(self) -> bool:
        status = await check_ollama_status_async()
        return bool(status.get("ok"))

    def is_available(self) -> bool:
        return _run_sync(self.is_available_async())

    async def get_status_models_async(self) -> list[dict[str, Any]]:
        status = await check_ollama_status_async()
        if not status.get("ok"):
            return []
        vision_names = set(status.get("vision_models", []))
        return [
            ScannerModelInfo(
                name=model_name,
                provider="vision" if model_name in vision_names else "text",
                kind="cloud" if _is_cloud_model(model_name) else "local",
                available=True,
                working=True,
                status_label="bereit",
            ).model_dump()
            for model_name in status.get("models", [])
        ]

    def get_status_models(self) -> list[dict[str, Any]]:
        return _run_sync(self.get_status_models_async())

    async def get_vision_model_names_async(self) -> list[str]:
        status = await check_ollama_status_async()
        if not status.get("ok"):
            return []
        return list(status.get("vision_models", []))

    def get_vision_model_names(self) -> list[str]:
        return _run_sync(self.get_vision_model_names_async())

    async def get_best_model_async(self) -> str | None:
        status = await check_ollama_status_async()
        if not status.get("ok"):
            return None
        return status.get("best_vision")

    def get_best_model(self) -> str | None:
        return _run_sync(self.get_best_model_async())

    async def get_pipeline_async(self) -> list[ScannerPipelineInfo]:
        vision_models = await self.get_vision_model_names_async()
        available = await self.is_available_async()
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
                models=vision_models[:3],
                available=available,
                status_label="bereit" if available else "nicht erreichbar",
            ),
            ScannerPipelineInfo(step=3, type="classification"),
        ]

    def get_pipeline(self) -> list[ScannerPipelineInfo]:
        return _run_sync(self.get_pipeline_async())

    async def extract_async(
        self,
        scanner_file: ScannerFile,
        selected_model: str = "",
        preferred_models: list[str] | None = None,
    ) -> ProviderExtractionResult:
        vision_models = await self.get_vision_model_names_async()
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

            data = await extract_invoice_async(scanner_file.content, model_name)
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

    def extract(
        self,
        scanner_file: ScannerFile,
        selected_model: str = "",
        preferred_models: list[str] | None = None,
    ) -> ProviderExtractionResult:
        return _run_sync(self.extract_async(scanner_file, selected_model, preferred_models))

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