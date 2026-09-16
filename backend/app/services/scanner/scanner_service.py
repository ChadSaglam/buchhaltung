from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scanner_config import ScannerConfig
from app.models.user import User
from app.schemas.scanner import (
    ExtractedInvoice,
    ScannerConfigResponse,
    ScannerConfigUpdate,
    ScannerExtractResponse,
    ScannerStatusResponse,
)
from app.services.classifier import TenantClassifier, calc_mwst, vat_code_for
from app.services.ollama_vision import parse_invoice_text
from app.services.plan_limits import PlanLimits
from app.services.receipts import store_receipt
from app.services.scanner.base import ScannerFile
from app.services.scanner.registry import ScannerProviderRegistry
from app.services.storage_quota import StorageQuota
from app.services.usage_meter import UsageMeter

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024
CUSTOM_MODEL_NAME = "custom-ocr"


class ScannerService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.registry = ScannerProviderRegistry()

    async def get_status(self) -> ScannerStatusResponse:
        vision = self.registry.get_vision_provider("ollama")
        custom_available = self.registry.custom_ocr_available()
        config = await self.get_or_create_config_model()

        # B-49: every probe below hits the (cached) Ollama status once, on the event loop —
        # no sync shims spinning up a thread + a second loop per call.
        vision_ok = await vision.is_available_async()
        best_vision = config.default_ollama_model or await vision.get_best_model_async()
        if custom_available and not config.default_ollama_model:
            best_vision = CUSTOM_MODEL_NAME

        return ScannerStatusResponse(
            ok=vision_ok or custom_available,
            error=None
            if (vision_ok or custom_available)
            else "Scanner nicht verfügbar (kein Vision-Modell und keine OCR).",
            models=await self.registry.list_status_models_async(),
            vision_models=await vision.get_vision_model_names_async(),
            best_vision=best_vision,
            scanner_mode="custom-first" if custom_available else "vision-only",
            pipeline=await vision.get_pipeline_async(),
            custom_ocr_available=custom_available,
        )

    async def get_or_create_config_model(self) -> ScannerConfig:
        stmt = select(ScannerConfig).where(ScannerConfig.tenant_id == self.user.tenant_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if config is not None:
            return config

        config = ScannerConfig(
            tenant_id=self.user.tenant_id,
            ocr_provider="custom-ocr",
            vision_provider="ollama",
            fallback_provider="ollama",
            ollama_base_url="http://localhost:11434",
            default_ollama_model=None,
            ocr_command=None,
            pdf_ocr_enabled=True,
            invoice_matching_enabled=True,
            auto_classification_enabled=True,
        )
        self.db.add(config)
        try:
            await self.db.commit()
        except IntegrityError:
            # Two requests of the same tenant raced on the first call (the
            # dashboard fires several status calls at once). The other one
            # won; use its row.
            await self.db.rollback()
            result = await self.db.execute(stmt)
            return result.scalar_one()
        await self.db.refresh(config)
        return config

    async def get_config(self) -> ScannerConfigResponse:
        config = await self.get_or_create_config_model()
        return ScannerConfigResponse.model_validate(config)

    async def update_config(self, payload: ScannerConfigUpdate) -> ScannerConfigResponse:
        config = await self.get_or_create_config_model()

        config.ocr_provider = payload.ocr_provider
        config.vision_provider = payload.vision_provider
        config.fallback_provider = payload.fallback_provider
        config.default_ollama_model = payload.default_ollama_model
        config.pdf_ocr_enabled = payload.pdf_ocr_enabled
        config.invoice_matching_enabled = payload.invoice_matching_enabled
        config.auto_classification_enabled = payload.auto_classification_enabled

        await self.db.commit()
        await self.db.refresh(config)
        return ScannerConfigResponse.model_validate(config)

    async def extract(
        self,
        *,
        file_name: str,
        content_type: str,
        content: bytes,
        model: str = "",
        on_step: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        bereits_gespeichert: str | None = None,
    ) -> ScannerExtractResponse:
        """Extract one document. ``on_step`` receives every pipeline step as it happens (B-15).

        ``bereits_gespeichert`` ist der Schlüssel einer Datei, die der Aufrufer
        schon abgelegt hat. `DocumentService.ingest` speichert den Beleg selbst
        (B-09) und ruft dann hier an, wenn kein QR-Code gefunden wurde — ohne
        diesen Parameter landete **jede Rechnung ohne QR-Code zweimal** im
        Speicher, unter zwei Schlüsseln, und zählte zweimal gegen die Quote
        (B-54) und gegen den Beleg-Zähler (B-23).
        """
        steps: list[dict[str, Any]] = []

        async def emit(step: dict[str, Any]) -> None:
            steps.append(step)
            if on_step is not None:
                await on_step(step)

        self._validate_upload(content_type=content_type, content=content)
        if bereits_gespeichert:
            source_key = bereits_gespeichert
            await emit({"icon": "📤", "label": "Datei wird gespeichert", "status": "done"})
        else:
            # Audit copy first (B-09): the document survives even if extraction fails.
            # Which is exactly why the quota has to answer before it is written (B-54).
            # B-23: derselbe Beleg-Zähler wie beim Upload über Belege — es ist
            # derselbe Vorgang, nur eine andere Tür.
            await PlanLimits(self.user.tenant_id, self.db).ensure("belege")
            quota = StorageQuota(self.user.tenant_id, self.db)
            await quota.ensure_room_for(len(content))
            await emit({"icon": "📤", "label": "Datei wird gespeichert", "status": "active"})
            source_key = await asyncio.to_thread(
                store_receipt, self.user.tenant_id, filename=file_name, content_type=content_type, content=content
            )
            await quota.record(len(content))
            await UsageMeter(self.user.tenant_id, self.db).record("beleg")
            steps[-1]["status"] = "done"
        scanner_file = ScannerFile(
            filename=file_name,
            content_type=content_type,
            content=content,
        )

        config = await self.get_or_create_config_model()
        ocr = self.registry.get_ocr_provider(config.ocr_provider)
        vision = self.registry.get_vision_provider(config.vision_provider)

        status = await self.get_status()
        if not status.ok:
            raise HTTPException(503, status.error or "Scanner nicht verfügbar.")

        attempts: list[dict[str, Any]] = []
        providers: list[dict[str, str]] = []

        data: dict[str, Any] | None = None
        ocr_provider: str | None = None
        ocr_worked = False
        vision_model: str | None = None
        custom_available = ocr.is_available()

        effective_model = (model or config.default_ollama_model or "").strip()

        if self._use_custom_first(effective_model):
            await emit({"icon": "🔎", "label": "OCR (Tesseract) läuft", "status": "active", "provider": "ocr"})
            ocr_result = await ocr.extract_async(scanner_file)
            steps[-1]["status"] = "done" if ocr_result.data else "failed"
            for item in ocr_result.steps:
                await emit(item.model_dump())
            attempts.extend(item.model_dump() for item in ocr_result.attempts)
            providers.extend(ocr_result.providers)
            if ocr_result.data and ocr_result.data.get("ocr_text"):
                parsed = parse_invoice_text(ocr_result.data["ocr_text"])
                if parsed:
                    data = parsed
                    ocr_provider = ocr_result.ocr_provider
                    ocr_worked = True
                    await emit(
                        {
                            "icon": "📝",
                            "label": "Rechnungsdetails aus OCR-Text extrahiert",
                            "status": "done",
                            "provider": "ocr",
                            "model": ocr_result.ocr_provider,
                        }
                    )

        if not data and await vision.is_available_async():
            await emit(
                {
                    "icon": "🤖",
                    "label": f"Vision-Modell {effective_model or 'automatisch'} liest die Rechnung",
                    "status": "active",
                    "provider": "vision",
                    "model": effective_model or None,
                }
            )
            vision_result = await vision.extract_async(
                scanner_file=scanner_file,
                selected_model=effective_model,
                preferred_models=["gemma3:12b", "gemma3:4b", "kimi-k2.5:cloud"],
            )
            steps[-1]["status"] = "done" if vision_result.data else "failed"
            for item in vision_result.steps:
                await emit(item.model_dump())
            attempts.extend(item.model_dump() for item in vision_result.attempts)
            providers.extend(vision_result.providers)

            if vision_result.data:
                data = vision_result.data
                vision_model = vision_result.selected_model
                if not ocr_provider:
                    ocr_provider = vision_result.ocr_provider
            elif not data:
                raise HTTPException(422, vision_result.error or "Keine Rechnung erkannt.")

        if not data:
            raise HTTPException(422, "Keine Rechnung erkannt.")

        if config.auto_classification_enabled:
            await emit(
                {
                    "icon": "🧠",
                    "label": "Kontierung wird berechnet",
                    "status": "active",
                    "provider": "classification",
                }
            )
            data = await self._classify_invoice(data)
            steps[-1]["status"] = "done"

            best_conf = data.get("classification_confidence") or 0
            best_source = data.get("classification_source") or ""
            await emit(
                {
                    "icon": "🎯",
                    "label": f"Kontierung: {data.get('kt_soll', '')}/{data.get('kt_haben', '')} ({best_source}, {best_conf:.0%})",
                    "status": "done",
                    "provider": "classification",
                    "source": best_source,
                    "confidence": best_conf,
                }
            )

        data["source_key"] = source_key
        data["vision_model"] = vision_model or ""
        data["ocr_provider"] = ocr_provider or ""
        data["ocr_worked"] = ocr_worked
        data["custom_ocr_available"] = custom_available
        data["scanner_steps"] = steps
        data["scanner_attempts"] = attempts
        data["scanner_providers"] = providers

        return ScannerExtractResponse(data=ExtractedInvoice(**data))

    async def extract_events(self, **kwargs: Any) -> AsyncIterator[str]:
        """``extract`` as Server-Sent Events: ``step`` frames while it runs, then ``result`` or ``error`` (B-15)."""
        queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

        async def on_step(step: dict[str, Any]) -> None:
            await queue.put(("step", step))

        async def run() -> None:
            try:
                response = await self.extract(on_step=on_step, **kwargs)
                await queue.put(("result", response.model_dump(mode="json")))
            except HTTPException as exc:
                await queue.put(("error", {"status": exc.status_code, "message": str(exc.detail)}))
            except Exception:
                logger.exception("[SCANNER] extract failed while streaming")
                await queue.put(("error", {"status": 500, "message": "Scanner-Fehler."}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while (item := await queue.get()) is not None:
                event, payload = item
                yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    def _validate_upload(self, *, content_type: str, content: bytes) -> None:
        if not content_type or not (content_type.startswith("image") or content_type == "application/pdf"):
            raise HTTPException(400, "Nur Bilder (JPG, PNG, WebP) oder PDF erlaubt.")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"Datei zu gross (max {MAX_FILE_SIZE // 1024 // 1024} MB).")

    def _use_custom_first(self, selected_model: str) -> bool:
        selected = (selected_model or "").strip()
        return not selected or selected == CUSTOM_MODEL_NAME

    async def _classify_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        vendor = str(data.get("vendor", "") or "")
        description = str(data.get("description", "") or "")
        total_amount = float(data.get("total_amount", 0) or 0)
        vat_rate = self._normalize_vat_rate(data.get("vat_rate", 0))

        is_credit = any(
            kw in f"{vendor} {description}".lower() for kw in ["gutschrift", "zahlung erhalten", "einzahlung"]
        )

        clf = TenantClassifier(self.user.tenant_id, self.db)
        candidates = [
            vendor.strip(),
            f"{vendor} {description.split('(')[0].split(',')[0]}".strip(),
            f"{vendor} {description}".strip(),
            description.strip(),
        ]
        candidates = [candidate for candidate in candidates if candidate]

        best_result = None
        best_input = ""
        for text in candidates:
            result = await clf.classify(text, is_credit, total_amount)
            if best_result is None or result.confidence > best_result.confidence:
                best_result = result
                best_input = text
            if result.confidence >= 0.7:
                break

        if best_result is None:
            raise HTTPException(422, "Klassifizierung fehlgeschlagen.")

        # B-48: the rate on the receipt decides pct and code exactly — no ">= 7 means 8.1".
        vat = vat_code_for(vat_rate, best_result.mwst_code or "") if vat_rate > 0 else None
        if vat:
            best_result.mwst_pct, best_result.mwst_code = vat
            best_result.mwst_amount = calc_mwst(total_amount, best_result.mwst_pct)

        result_data = dict(data)
        result_data["kt_soll"] = best_result.kt_soll
        result_data["kt_haben"] = best_result.kt_haben
        result_data["mwst_code"] = best_result.mwst_code
        result_data["mwst_pct"] = best_result.mwst_pct
        result_data["mwst_amount"] = best_result.mwst_amount
        result_data["classification_confidence"] = best_result.confidence
        result_data["classification_source"] = best_result.source
        result_data["classification_input"] = best_input
        return result_data

    def _normalize_vat_rate(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
